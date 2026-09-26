import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template(
            "register.html",
            error="All fields are required.",
            name=name, email=email,
        )

    if "@" not in email:
        return render_template(
            "register.html",
            error="Enter a valid email address.",
            name=name, email=email,
        )

    if len(password) < 8:
        return render_template(
            "register.html",
            error="Password must be at least 8 characters.",
            name=name, email=email,
        )

    if get_user_by_email(email) is not None:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name, email=email,
        )

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name, email=email,
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html",
            error="Invalid email or password.",
            email=email,
        )

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": session.get("user_name", "Aditi Sharma"),
        "email": "aditi.sharma@example.com",
        "created_at": "2024-11-03",
    }
    initials = "".join(part[0].upper() for part in user["name"].split()[:2])

    expenses = [
        {"date": "2026-09-24", "description": "Swiggy dinner order", "category": "Food", "amount": 640},
        {"date": "2026-09-22", "description": "Ola cab to airport", "category": "Transport", "amount": 890},
        {"date": "2026-09-20", "description": "Electricity bill", "category": "Bills", "amount": 2150},
        {"date": "2026-09-18", "description": "Pharmacy purchase", "category": "Health", "amount": 480},
        {"date": "2026-09-15", "description": "Movie tickets - PVR", "category": "Entertainment", "amount": 720},
        {"date": "2026-09-12", "description": "Myntra order", "category": "Shopping", "amount": 1899},
    ]

    stats = {
        "total_spent": sum(expense["amount"] for expense in expenses),
        "transaction_count": len(expenses),
        "top_category": "Food",
    }

    category_breakdown = [
        {"category": "Food", "total": 6420, "percent": 38},
        {"category": "Bills", "total": 4300, "percent": 26},
        {"category": "Shopping", "total": 3100, "percent": 19},
        {"category": "Transport", "total": 1780, "percent": 11},
        {"category": "Entertainment", "total": 990, "percent": 6},
    ]

    return render_template(
        "profile.html",
        user=user,
        initials=initials,
        expenses=expenses,
        stats=stats,
        category_breakdown=category_breakdown,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()

    app.run(debug=True, port=5001)
