from flask import Flask, render_template, request, url_for
import requests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from units import unit, UnitError

app = Flask(__name__)

app.jinja_env.globals['datetime'] = datetime

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mealplanner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

API_BASE_URL = "https://www.themealdb.com/api/json/v1/1/"


class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    meal_id = db.Column(db.String(10), nullable=False)
    meal_title = db.Column(db.String(255), nullable=False)
    meal_image_url = db.Column(db.String(255), nullable=False)
    ingredients = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    area = db.Column(db.String(50), nullable=True)
    tags = db.Column(db.String(255), nullable=True)
    youtube_url = db.Column(db.String(255), nullable=True)
    source_url = db.Column(db.String(255), nullable=True)


def fetch_random_meal():
    response = requests.get(API_BASE_URL + "random.php")
    data = response.json()
    return data['meals'][0]


def fetch_meal_by_id(meal_id):
    response = requests.get(f'https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}')
    meal = response.json()['meals'][0]
    return meal


def save_meal_to_plan(day, meal_id, offset):
    meal = fetch_meal_by_id(meal_id)
    meal_title = meal['strMeal']
    meal_image_url = meal['strMealThumb']
    ingredients = ', '.join(
        [f"{meal[f'strIngredient{i}']} {meal[f'strMeasure{i}']}" for i in range(1, 21) if meal[f'strIngredient{i}']])
    instructions = meal['strInstructions']
    category = meal['strCategory']
    area = meal['strArea']
    tags = meal['strTags']
    youtube_url = meal['strYoutube']
    source_url = meal['strSource']

    date_obj = date.fromisoformat(day)

    # Update the date based on the offset
    date_obj += timedelta(weeks=offset)

    meal_plan_entry = MealPlan.query.filter_by(date=date_obj).first()

    if meal_plan_entry:
        meal_plan_entry.meal_id = meal_id
        meal_plan_entry.meal_title = meal_title
        meal_plan_entry.meal_image_url = meal_image_url
        meal_plan_entry.ingredients = ingredients
        meal_plan_entry.instructions = instructions
        meal_plan_entry.category = category
        meal_plan_entry.area = area
        meal_plan_entry.tags = tags
        meal_plan_entry.youtube_url = youtube_url
        meal_plan_entry.source_url = source_url
    else:
        meal_plan_entry = MealPlan(date=date_obj, meal_id=meal_id, meal_title=meal_title, meal_image_url=meal_image_url,
                                   ingredients=ingredients, instructions=instructions, category=category, area=area,
                                   tags=tags, youtube_url=youtube_url, source_url=source_url)
        db.session.add(meal_plan_entry)

    db.session.commit()


@app.route('/')
@app.route('/week')
def index():
    offset = int(request.args.get('offset', 0))
    week_start_date = date.today() - timedelta(days=date.today().weekday()) + timedelta(weeks=offset)
    meal_plan_entries = MealPlan.query.filter(MealPlan.date >= week_start_date,
                                              MealPlan.date < week_start_date + timedelta(weeks=1)).all()
    meal_plan_content = {week_start_date + timedelta(days=i): None for i in range(7)}

    for entry in meal_plan_entries:
        meal_plan_content[entry.date] = {
            'id': entry.meal_id,
            'title': entry.meal_title,
            'image_url': entry.meal_image_url
        }

    # Convert datetime.date objects to strings in the meal_plan_content dictionary
    meal_plan_str = {str(k): v for k, v in meal_plan_content.items()}

    meal = fetch_random_meal()
    prev_week_offset = offset - 1
    next_week_offset = offset + 1
    return render_template('index.html', meal=meal,
                           meal_plan_content=meal_plan_str,
                           prev_week_offset=prev_week_offset,
                           next_week_offset=next_week_offset)


@app.route('/accept_meal')
def accept_meal():
    day = request.args.get('day')
    meal_id = request.args.get('meal_id')
    offset = int(request.args.get('offset', 0))
    save_meal_to_plan(day, meal_id, offset)
    return "Success", 200


@app.route('/remove_meal')
def remove_meal():
    day = request.args.get('day')
    meal_plan_entry = MealPlan.query.filter_by(date=day).first()
    if meal_plan_entry:
        db.session.delete(meal_plan_entry)
    db.session.commit()
    return "Success", 200


@app.route('/meal_details/<int:meal_id>')
def meal_details(meal_id):
    meal = fetch_meal_by_id(meal_id)
    return render_template('meal_details.html', meal=meal)


@app.route('/shopping_list')
def shopping_list():
    meal_plan_entries = MealPlan.query.all()
    shopping_list = {}
    for entry in meal_plan_entries:
        ingredients_list = entry.ingredients.split(", ")
        for ingredient in ingredients_list:
            name, quantity = ingredient.rsplit(" ", 1)
            if not quantity:
                continue
            if name in shopping_list:
                try:
                    shopping_list[name] += unit(quantity)
                except UnitError:
                    shopping_list[name] = str(shopping_list[name]) + ' + ' + quantity
            else:
                try:
                    shopping_list[name] = unit(quantity)
                except UnitError:
                    shopping_list[name] = quantity

    # Convert units back to strings for rendering in the template
    shopping_list_str = {k: str(v) for k, v in shopping_list.items()}

    return render_template('shopping_list.html', shopping_list=shopping_list_str)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        app.run(host='0.0.0.0', debug=True)
