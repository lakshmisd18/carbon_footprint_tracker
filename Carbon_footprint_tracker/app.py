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

# ✅ IMPORTANT FOR RENDER
with app.app_context():
    db.create_all()

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

# -------------------- HOME --------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")

        if not email:
            return "Email required", 400

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                name=email.split("@")[0],
                email=email,
                role="user"
            )
            db.session.add(user)
            db.session.commit()

        session["user_id"] = user.id
        return redirect(url_for("dashboard", user_id=user.id))

    return render_template("login.html")

# -------------------- LOGOUT --------------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==================== USER DASHBOARD ====================
@app.route("/dashboard/<int:user_id>")
@login_required
def dashboard(user_id):
    user = User.query.get_or_404(user_id)
    activities = Activity.query.filter_by(user_id=user_id).all()
    total_emission = sum(a.emission for a in activities)

    return render_template(
        "dashboard.html",
        user=user,
        activities=activities,
        total_emission=round(total_emission, 2)
    )

# ==================== ADD ACTIVITY ====================
@app.route("/add_activity/<int:user_id>", methods=["POST"])
@login_required
def add_activity(user_id):
    activity_type = request.form.get("activity_type", "").lower()
    value = float(request.form.get("value", 0))

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
