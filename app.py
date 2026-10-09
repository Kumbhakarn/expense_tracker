import calendar
import os
import sqlite3
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

RECENT_TRANSACTIONS_LIMIT = 10

app = Flask(__name__)
# No guessable fallback: without SECRET_KEY, use a random per-process key
# (sessions reset on restart, but cookies can't be forged).
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)


@app.template_filter("inr")
def format_inr(amount):
    """Format a number as rupees, e.g. 1234.5 -> '₹1,234.50'."""
    return f"₹{amount:,.2f}"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    """Return a normalised 'YYYY-MM-DD' string, or None if missing/malformed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _resolve_date_filter(args):
    """Return (date_from, date_to, filter_error) from the request query args."""
    date_from = _parse_iso_date(args.get("date_from"))
    date_to = _parse_iso_date(args.get("date_to"))
    if not (date_from and date_to):
        return None, None, None
    # Safe as string comparison: both are zero-padded ISO dates.
    if date_from > date_to:
        return None, None, "Start date must be before end date."
    return date_from, date_to, None


def _months_ago(day, months):
    """Return `day` shifted back by `months`, clamping to the month's last day."""
    year, month = divmod(day.year * 12 + (day.month - 1) - months, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def _date_presets(today):
    """Return the quick-select filter presets relative to `today`."""
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return [
        {"key": "this_month", "label": "This Month",
         "date_from": month_start.isoformat(), "date_to": month_end.isoformat()},
        {"key": "last_3_months", "label": "Last 3 Months",
         "date_from": _months_ago(today, 3).isoformat(), "date_to": today.isoformat()},
        {"key": "last_6_months", "label": "Last 6 Months",
         "date_from": _months_ago(today, 6).isoformat(), "date_to": today.isoformat()},
        {"key": "all_time", "label": "All Time", "date_from": None, "date_to": None},
    ]


def _active_filter_key(presets, date_from, date_to):
    """Return the matching preset key, or 'custom'.

    An ignored (invalid or partial) filter resolves to (None, None), which
    matches the All Time preset.
    """
    for preset in presets:
        if (preset["date_from"], preset["date_to"]) == (date_from, date_to):
            return preset["key"]
    return "custom"


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
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    initials = "".join(part[0].upper() for part in user["name"].split()[:2])

    date_from, date_to, filter_error = _resolve_date_filter(request.args)
    presets = _date_presets(date.today())

    return render_template(
        "profile.html",
        user=user,
        initials=initials,
        expenses=get_recent_transactions(
            user_id, RECENT_TRANSACTIONS_LIMIT, date_from, date_to,
        ),
        transaction_limit=RECENT_TRANSACTIONS_LIMIT,
        stats=get_summary_stats(user_id, date_from, date_to),
        category_breakdown=get_category_breakdown(user_id, date_from, date_to),
        presets=presets,
        active_filter=_active_filter_key(presets, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        filter_error=filter_error,
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
