from flask import Flask, render_template, request, redirect, url_for, session, abort
from datetime import datetime
from collections import defaultdict
import json
from functools import wraps

from models import db, User, Activity

app = Flask(__name__)
app.secret_key = "secret123"

# -------------------- DATABASE CONFIG --------------------

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///carbon_footprint.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# -------------------- EMISSION FACTORS --------------------

EMISSION_FACTORS = {
    "transport": 0.21,
    "electricity": 0.82,
    "food": 2.5
}

# -------------------- AUTH DECORATORS --------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = User.query.get(session.get("user_id"))
        if not user or user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# -------------------- LOGIN --------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        role = request.form["role"].lower()

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(name=name, email=email, role=role)
            db.session.add(user)
        else:
            user.role = role

        db.session.commit()
        session["user_id"] = user.id

        if role == "admin":
            return redirect(url_for("admin_dashboard", admin_id=user.id))
        else:
            return redirect(url_for("dashboard", user_id=user.id))

    return render_template("login.html")

# -------------------- LOGOUT --------------------

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==================== ADMIN DASHBOARD ====================

@app.route("/admin/<int:admin_id>")
def admin_dashboard(admin_id):
    admin = User.query.get_or_404(admin_id)
    if admin.role != "admin":
        abort(403)

    users = User.query.all()
    activities = Activity.query.all()

    total_users = len(users)
    total_activities = len(activities)
    total_emission = sum(a.emission for a in activities)

    category_emission = defaultdict(float)
    for a in activities:
        category_emission[a.activity_type] += a.emission

    monthly_emission = defaultdict(float)
    for a in activities:
        month = a.date.strftime("%Y-%m")
        monthly_emission[month] += a.emission

    sorted_months = sorted(monthly_emission.keys())
    monthly_values = [monthly_emission[m] for m in sorted_months]

    user_emissions = defaultdict(float)
    for a in activities:
        user_emissions[a.user_id] += a.emission

    top_users = sorted(user_emissions.items(), key=lambda x: x[1], reverse=True)[:5]

    top_user_labels = []
    top_user_values = []

    for uid, emission in top_users:
        user = User.query.get(uid)
        top_user_labels.append(user.name)
        top_user_values.append(round(emission, 2))

    recent_activities = Activity.query.order_by(Activity.date.desc()).limit(5).all()

    return render_template(
        "admin_dashboard.html",
        admin=admin,
        total_users=total_users,
        total_activities=total_activities,
        total_emission=round(total_emission, 2),
        transport_emission=round(category_emission.get("transport", 0), 2),
        electricity_emission=round(category_emission.get("electricity", 0), 2),
        food_emission=round(category_emission.get("food", 0), 2),
        monthly_labels=json.dumps(sorted_months),
        monthly_values=json.dumps(monthly_values),
        top_user_labels=json.dumps(top_user_labels),
        top_user_values=json.dumps(top_user_values),
        recent_activities=recent_activities
    )

# ==================== USER DASHBOARD ====================

@app.route("/dashboard/<int:user_id>")
def dashboard(user_id):
    user = User.query.get_or_404(user_id)
    month_filter = request.args.get("month")

    if month_filter:
        activities = Activity.query.filter(
            Activity.user_id == user_id,
            Activity.date.like(f"{month_filter}%")
        ).all()
    else:
        activities = Activity.query.filter_by(user_id=user_id).all()

    total_emission = sum(a.emission for a in activities)

    monthly_emission = defaultdict(float)
    for a in activities:
        month = a.date.strftime("%Y-%m")
        monthly_emission[month] += a.emission

    sorted_months = sorted(monthly_emission.keys())
    monthly_values = [monthly_emission[m] for m in sorted_months]

    return render_template(
        "dashboard.html",
        user=user,
        activities=activities,
        total_emission=round(total_emission, 2),
        monthly_labels=json.dumps(sorted_months),
        monthly_values=json.dumps(monthly_values),
        selected_month=month_filter
    )

# ==================== ADD ACTIVITY ====================

@app.route("/add_activity/<int:user_id>", methods=["POST"])
def add_activity(user_id):
    activity_type = request.form["activity_type"].lower().strip()
    value = float(request.form["value"])

    emission = value * EMISSION_FACTORS.get(activity_type, 0)

    activity = Activity(
        activity_type=activity_type,
        value=value,
        emission=emission,
        date=datetime.now(),
        user_id=user_id
    )

    db.session.add(activity)
    db.session.commit()

    return redirect(url_for("dashboard", user_id=user_id))

# ==================== MAIN ====================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
