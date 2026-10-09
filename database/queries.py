from database.db import get_db

_DATE_CLAUSE = " AND date BETWEEN ? AND ?"


def _date_filter(date_from, date_to):
    """Return (sql_fragment, params). The filter applies only when both bounds are set."""
    if date_from and date_to:
        return _DATE_CLAUSE, (date_from, date_to)
    return "", ()


def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {total_spent, transaction_count, top_category} for the range.

    top_category is None when the range has no expenses.
    """
    clause, date_params = _date_filter(date_from, date_to)
    params = (user_id, *date_params)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_spent,"
            " COUNT(*) AS transaction_count"
            " FROM expenses WHERE user_id = ?" + clause,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause
            + " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": round(totals["total_spent"], 2),
        "transaction_count": totals["transaction_count"],
        "top_category": top["category"] if top else None,
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return the latest `limit` expenses in the range as dicts, newest first."""
    clause, date_params = _date_filter(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount"
            " FROM expenses WHERE user_id = ?" + clause
            + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return [{category, total, percent}] for the range, largest first.

    percent is an integer share of the range's total; [] when empty.
    """
    clause, date_params = _date_filter(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total"
            " FROM expenses WHERE user_id = ?" + clause
            + " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)
    return [
        {
            "category": row["category"],
            "total": round(row["total"], 2),
            "percent": round(row["total"] / grand_total * 100) if grand_total else 0,
        }
        for row in rows
    ]
