import re
from datetime import date

import pytest

import app as app_module
from conftest import login_as
from database import db, queries

RUPEE = "₹"
PROFILE = "/profile"


def _get(client, **params):
    resp = client.get(PROFILE, query_string=params)
    return resp, resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# _parse_iso_date
# ---------------------------------------------------------------------------
class TestParseIsoDate:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("2026-03-05", "2026-03-05"),
            ("2026-1-5", "2026-01-05"),
            ("2024-02-29", "2024-02-29"),
        ],
    )
    def test_parse_iso_date_valid_returns_normalised(self, value, expected):
        assert app_module._parse_iso_date(value) == expected

    @pytest.mark.parametrize(
        "value",
        ["", None, "not-a-date", "2026-13-01", "2026-02-30", "2025-02-29",
         "05/03/2026", "'; DROP TABLE expenses;--"],
    )
    def test_parse_iso_date_invalid_returns_none(self, value):
        assert app_module._parse_iso_date(value) is None


# ---------------------------------------------------------------------------
# _resolve_date_filter
# ---------------------------------------------------------------------------
class TestResolveDateFilter:
    def test_resolve_both_valid_returns_range(self):
        assert app_module._resolve_date_filter(
            {"date_from": "2026-03-01", "date_to": "2026-03-31"}
        ) == ("2026-03-01", "2026-03-31", None)

    def test_resolve_same_day_is_allowed(self):
        assert app_module._resolve_date_filter(
            {"date_from": "2026-03-01", "date_to": "2026-03-01"}
        ) == ("2026-03-01", "2026-03-01", None)

    def test_resolve_no_params_returns_all_none(self):
        assert app_module._resolve_date_filter({}) == (None, None, None)

    def test_resolve_reversed_returns_error(self):
        assert app_module._resolve_date_filter(
            {"date_from": "2026-04-01", "date_to": "2026-03-01"}
        ) == (None, None, "Start date must be before end date.")

    @pytest.mark.parametrize("args", [
        {"date_from": "2026-03-01"},
        {"date_to": "2026-03-31"},
    ])
    def test_resolve_single_bound_ignored(self, args):
        assert app_module._resolve_date_filter(args) == (None, None, None)

    @pytest.mark.parametrize("args", [
        {"date_from": "garbage", "date_to": "2026-03-31"},
        {"date_from": "garbage", "date_to": "also-garbage"},
    ])
    def test_resolve_malformed_falls_back_without_error(self, args):
        assert app_module._resolve_date_filter(args) == (None, None, None)


# ---------------------------------------------------------------------------
# _months_ago and _date_presets
# ---------------------------------------------------------------------------
class TestMonthsAgo:
    @pytest.mark.parametrize(
        "start,n,expected",
        [
            (date(2026, 5, 31), 3, date(2026, 2, 28)),
            (date(2024, 5, 31), 3, date(2024, 2, 29)),
            (date(2026, 1, 15), 3, date(2025, 10, 15)),
            (date(2026, 10, 10), 6, date(2026, 4, 10)),
            (date(2026, 8, 31), 1, date(2026, 7, 31)),
            (date(2026, 3, 31), 1, date(2026, 2, 28)),
        ],
    )
    def test_months_ago_clamps_and_wraps_year(self, start, n, expected):
        assert app_module._months_ago(start, n) == expected


class TestDatePresets:
    TODAY = date(2026, 10, 10)

    def _by_key(self):
        return {p["key"]: p for p in app_module._date_presets(self.TODAY)}

    def test_presets_have_expected_keys_and_fields(self):
        presets = self._by_key()
        assert set(presets) == {
            "this_month", "last_3_months", "last_6_months", "all_time"
        }
        for p in presets.values():
            assert {"key", "label", "date_from", "date_to"} <= set(p)

    def test_presets_all_time_has_no_bounds(self):
        p = self._by_key()["all_time"]
        assert p["date_from"] is None and p["date_to"] is None

    def test_presets_this_month_is_full_calendar_month(self):
        p = self._by_key()["this_month"]
        assert p["date_from"] == "2026-10-01"
        assert p["date_to"] == "2026-10-31"

    def test_presets_rolling_windows_end_today(self):
        presets = self._by_key()
        assert presets["last_3_months"]["date_to"] == "2026-10-10"
        assert presets["last_6_months"]["date_to"] == "2026-10-10"
        assert presets["last_3_months"]["date_from"] == "2026-07-10"
        assert presets["last_6_months"]["date_from"] == "2026-04-10"

    def test_presets_labels_present(self):
        labels = {p["label"] for p in app_module._date_presets(self.TODAY)}
        assert labels == {"This Month", "Last 3 Months", "Last 6 Months",
                          "All Time"}


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
class TestQueries:
    def test_summary_unfiltered(self, users):
        s = queries.get_summary_stats(users["a"])
        assert s["total_spent"] == pytest.approx(1100.0)
        assert s["transaction_count"] == 4
        assert s["top_category"] == "Bills"

    def test_summary_filtered_range(self, users):
        s = queries.get_summary_stats(users["a"], "2026-03-01", "2026-03-31")
        assert s["total_spent"] == pytest.approx(800.0)
        assert s["transaction_count"] == 2
        assert s["top_category"] == "Bills"

    def test_summary_bounds_are_inclusive(self, users):
        s = queries.get_summary_stats(users["a"], "2026-03-05", "2026-03-20")
        assert s["transaction_count"] == 2
        assert s["total_spent"] == pytest.approx(800.0)

    def test_summary_single_day_range(self, users):
        s = queries.get_summary_stats(users["a"], "2026-02-10", "2026-02-10")
        assert s["transaction_count"] == 1
        assert s["total_spent"] == pytest.approx(200.0)
        assert s["top_category"] == "Transport"

    def test_summary_empty_range(self, users):
        s = queries.get_summary_stats(users["a"], "2025-01-01", "2025-01-31")
        assert s["total_spent"] == 0
        assert s["transaction_count"] == 0
        assert s["top_category"] is None

    def test_summary_user_without_expenses(self, empty_user):
        s = queries.get_summary_stats(empty_user)
        assert s["total_spent"] == 0
        assert s["transaction_count"] == 0
        assert s["top_category"] is None

    def test_summary_only_one_bound_is_unfiltered(self, users):
        s = queries.get_summary_stats(users["a"], date_from="2026-03-01")
        assert s["transaction_count"] == 4
        s = queries.get_summary_stats(users["a"], date_to="2026-01-31")
        assert s["transaction_count"] == 4

    def test_summary_isolated_per_user(self, users):
        s = queries.get_summary_stats(users["b"])
        assert s["total_spent"] == pytest.approx(9999.0)
        assert s["transaction_count"] == 1
        assert s["top_category"] == "Shopping"

    def test_recent_unfiltered_ordered_date_desc(self, users):
        rows = queries.get_recent_transactions(users["a"])
        assert [r["date"] for r in rows] == [
            "2026-03-20", "2026-03-05", "2026-02-10", "2026-01-15"]
        assert {"id", "date", "description", "category", "amount"} <= set(rows[0])

    def test_recent_filtered_range(self, users):
        rows = queries.get_recent_transactions(
            users["a"], date_from="2026-02-01", date_to="2026-03-10")
        assert [r["description"] for r in rows] == ["Mar food", "Feb bus"]

    def test_recent_limit_applies_with_filter(self, users):
        rows = queries.get_recent_transactions(
            users["a"], limit=1, date_from="2026-01-01", date_to="2026-12-31")
        assert len(rows) == 1
        assert rows[0]["date"] == "2026-03-20"

    def test_recent_empty_range_returns_empty_list(self, users):
        rows = queries.get_recent_transactions(
            users["a"], date_from="2025-01-01", date_to="2025-01-31")
        assert list(rows) == []

    def test_recent_excludes_other_users(self, users):
        rows = queries.get_recent_transactions(users["a"])
        assert all(r["description"] != "Bob secret purchase" for r in rows)

    def test_breakdown_unfiltered(self, users):
        rows = queries.get_category_breakdown(users["a"])
        totals = {r["category"]: r["total"] for r in rows}
        assert totals == {"Bills": 500.0, "Food": 400.0, "Transport": 200.0}
        assert {r["category"]: r["percent"] for r in rows} == {
            "Bills": 45, "Food": 36, "Transport": 18}

    def test_breakdown_percent_relative_to_filtered_total(self, users):
        rows = queries.get_category_breakdown(
            users["a"], "2026-03-01", "2026-03-31")
        pct = {r["category"]: r["percent"] for r in rows}
        assert set(pct) == {"Food", "Bills"}
        # 62.5 / 37.5 round half-to-even to 62 / 38.
        assert pct == {"Bills": 62, "Food": 38}

    def test_breakdown_empty_range_returns_empty_list(self, users):
        assert list(queries.get_category_breakdown(
            users["a"], "2025-01-01", "2025-01-31")) == []

    def test_breakdown_isolated_per_user(self, users):
        rows = queries.get_category_breakdown(users["a"])
        assert "Shopping" not in {r["category"] for r in rows}

    def test_sql_injection_in_dates_is_harmless(self, users):
        # Sorts above every digit-led date, so a bound value matches nothing.
        payload = "x' OR '1'='1"
        s = queries.get_summary_stats(users["a"], payload, "2026-12-31")
        assert s["transaction_count"] == 0
        conn = db.get_db()
        try:
            n = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        finally:
            conn.close()
        assert n == 5


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------
class TestProfileAuth:
    def test_profile_unauthenticated_redirects_to_login(self, client):
        resp = client.get(PROFILE)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_session_user_missing_redirects_to_login(self, client, users):
        login_as(client, 99999)
        resp = client.get(PROFILE)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_filter_params_unauthenticated_still_redirects(self, client):
        resp = client.get(PROFILE, query_string={
            "date_from": "2026-03-01", "date_to": "2026-03-31"})
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestProfileUnfiltered:
    def test_profile_no_params_shows_all_data(self, auth_client):
        resp, html = _get(auth_client)
        assert resp.status_code == 200
        assert f"{RUPEE}1,100.00" in html
        for desc in ("Jan food", "Feb bus", "Mar food", "Mar bills"):
            assert desc in html, f"missing {desc}"
        assert "Bills" in html

    def test_profile_does_not_leak_other_users_data(self, auth_client):
        _, html = _get(auth_client)
        assert "Bob secret purchase" not in html
        assert "9,999.00" not in html

    def test_profile_other_user_sees_own_data_only(self, client, users):
        login_as(client, users["b"])
        resp, html = _get(client)
        assert resp.status_code == 200
        assert "Bob secret purchase" in html
        assert f"{RUPEE}9,999.00" in html
        assert "Mar food" not in html

    def test_profile_shows_user_name(self, auth_client):
        _, html = _get(auth_client)
        assert "Alice" in html

    def test_profile_all_time_link_is_clean_url(self, auth_client):
        _, html = _get(auth_client)
        assert 'href="/profile"' in html


class TestProfileFiltered:
    def test_profile_custom_range_filters_all_sections(self, auth_client):
        resp, html = _get(auth_client,
                          date_from="2026-03-01", date_to="2026-03-31")
        assert resp.status_code == 200
        assert f"{RUPEE}800.00" in html
        assert "Mar food" in html and "Mar bills" in html
        assert "Jan food" not in html and "Feb bus" not in html
        assert "Transport" not in html
        assert "width: 62%" in html and "width: 38%" in html

    def test_profile_range_bounds_inclusive(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-03-05", date_to="2026-03-20")
        assert "Mar food" in html and "Mar bills" in html

    def test_profile_filtered_amounts_keep_rupee_symbol(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-02-01", date_to="2026-02-28")
        assert f"{RUPEE}200.00" in html
        assert "$200.00" not in html

    def test_profile_empty_range_shows_empty_states(self, auth_client):
        resp, html = _get(auth_client,
                          date_from="2025-01-01", date_to="2025-01-31")
        assert resp.status_code == 200
        assert f"{RUPEE}0.00" in html
        assert "No transactions in this period." in html
        assert "No spending in this period." in html
        assert "—" in html

    def test_profile_user_without_expenses_no_error(self, client, empty_user):
        login_as(client, empty_user)
        resp, html = _get(client)
        assert resp.status_code == 200
        assert f"{RUPEE}0.00" in html
        assert "No transactions in this period." in html
        assert "No spending in this period." in html

    def test_profile_filter_does_not_leak_other_user(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-03-01", date_to="2026-03-31")
        assert "Bob secret purchase" not in html


class TestProfileInvalidFilters:
    def test_profile_reversed_range_shows_error_and_unfiltered(self, auth_client):
        resp, html = _get(auth_client,
                          date_from="2026-04-01", date_to="2026-03-01")
        assert resp.status_code == 200
        assert 'class="filter-error"' in html
        assert "Start date must be before end date." in html
        assert f"{RUPEE}1,100.00" in html
        assert "Jan food" in html

    @pytest.mark.parametrize("params", [
        {"date_from": "not-a-date", "date_to": "2026-03-31"},
        {"date_from": "2026-03-01", "date_to": "31/03/2026"},
        {"date_from": "not-a-date", "date_to": "also-bad"},
        {"date_from": "2026-02-30", "date_to": "2026-03-31"},
        {"date_from": "", "date_to": ""},
        {"date_from": "2026-03-01"},
        {"date_to": "2026-03-31"},
    ])
    def test_profile_malformed_or_partial_falls_back_silently(
            self, auth_client, params):
        resp, html = _get(auth_client, **params)
        assert resp.status_code == 200
        assert f"{RUPEE}1,100.00" in html
        assert 'class="filter-error"' not in html

    def test_profile_sql_injection_params_do_not_crash(self, auth_client):
        resp, _ = _get(auth_client,
                       date_from="2026-01-01' OR '1'='1",
                       date_to="'; DROP TABLE expenses;--")
        assert resp.status_code == 200
        _, html = _get(auth_client)
        assert f"{RUPEE}1,100.00" in html

    def test_profile_no_error_shown_for_valid_range(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-03-01", date_to="2026-03-31")
        assert 'class="filter-error"' not in html


class TestProfileFilterBar:
    def _preset_params(self, key):
        presets = {p["key"]: p
                   for p in app_module._date_presets(date.today())}
        p = presets[key]
        return {k: p[k] for k in ("date_from", "date_to") if p[k]}

    def test_profile_renders_all_preset_labels(self, auth_client):
        _, html = _get(auth_client)
        for label in ("This Month", "Last 3 Months", "Last 6 Months",
                      "All Time"):
            assert label in html, f"missing preset {label}"

    def test_profile_renders_date_inputs_and_apply(self, auth_client):
        _, html = _get(auth_client)
        assert 'type="date"' in html
        assert 'name="date_from"' in html
        assert 'name="date_to"' in html
        assert "Apply" in html

    def test_profile_no_params_marks_all_time_active(self, auth_client):
        _, html = _get(auth_client)
        assert "filter-preset is-active" in html
        assert "filter-custom is-active" not in html
        active = re.findall(r'<a[^>]*filter-preset is-active[^>]*>', html)
        assert len(active) == 1
        assert 'href="/profile"' in active[0]

    @pytest.mark.parametrize("key", ["this_month", "last_3_months",
                                     "last_6_months"])
    def test_profile_preset_range_marks_preset_active(self, auth_client, key):
        resp, html = _get(auth_client, **self._preset_params(key))
        assert resp.status_code == 200
        assert "filter-preset is-active" in html
        assert "filter-custom is-active" not in html
        assert len(re.findall(r"filter-preset is-active", html)) == 1

    def test_profile_custom_range_marks_custom_active(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-03-01", date_to="2026-03-31")
        assert "filter-custom is-active" in html
        assert "filter-preset is-active" not in html

    def test_profile_custom_range_prefills_inputs(self, auth_client):
        _, html = _get(auth_client,
                       date_from="2026-03-01", date_to="2026-03-31")
        assert 'value="2026-03-01"' in html
        assert 'value="2026-03-31"' in html

    def test_profile_non_padded_dates_are_normalised(self, auth_client):
        _, html = _get(auth_client, date_from="2026-3-1", date_to="2026-3-31")
        assert f"{RUPEE}800.00" in html
        assert 'value="2026-03-01"' in html


class TestRecentLimitHint:
    def test_hint_hidden_below_limit(self, auth_client):
        _, html = _get(auth_client)
        assert "Showing the latest" not in html

    def test_hint_shown_when_limit_reached(self, auth_client, users):
        conn = db.get_db()
        try:
            for day in range(1, 11):
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (users["a"], 1.0, "Other", f"2026-05-{day:02d}", f"May {day}"),
                )
            conn.commit()
        finally:
            conn.close()
        _, html = _get(auth_client)
        assert html.count('<span class="badge') == 10
        assert "Showing the latest 10 transactions in this period." in html


def test_inr_filter_formats_rupees():
    assert app_module.format_inr(1234.5) == "₹1,234.50"
    assert app_module.format_inr(0) == "₹0.00"
