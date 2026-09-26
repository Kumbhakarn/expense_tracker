# Spec: Login and Logout

## Overview
This step wires up real authentication behind the existing `/login` page and implements the currently-stubbed `/logout` route. `GET /login` today only renders a static form; this step adds `POST /login` to verify credentials against the `users` table (created in Step 1, populated in Step 2) and starts a Flask session for the authenticated user. `/logout` clears that session. This is the second authentication step in the Spendly roadmap and unblocks Step 4 (profile) and every later step that needs to know which user is currently signed in.

## Depends on
- Step 1 — Database Setup (`.claude/specs/01.database-setup.md`): requires `get_db()`, `init_db()`, and the `users` table.
- Step 2 — Registration (`.claude/specs/02-registration.md`): requires `get_user_by_email()` and real user rows with hashed passwords to log in against.

## Routes
- `GET /login` — renders the login form — public (already implemented, unchanged)
- `POST /login` — validates submitted email/password against the `users` table, starts a session on success and redirects to the landing page (`/`), or re-renders `login.html` with an error on failure — public
- `GET /logout` — clears the session and redirects to the landing page (`/`) — logged-in (replaces the current stub, which returns a raw string)

## Database changes
No schema or `database/db.py` changes. This step reuses `get_user_by_email(email)` (added in Step 2) to fetch the user row and verifies the password with `werkzeug.security.check_password_hash` against the stored `password_hash`. No new DB helper functions are needed.

## Templates
- **Create:** none
- **Modify:** `templates/login.html` — re-populate the submitted `email` value in the input after a failed login (`value="{{ email or '' }}"`), matching the pattern used in `register.html`
- **Modify:** `templates/base.html` — nav shows "Sign in" / "Get started" when no user is in session; shows the logged-in user's name and a "Log out" link (`url_for('logout')`) when `session.get('user_id')` is set

## Files to change
- `app.py` — set `app.secret_key`; change `/login` route to accept `["GET", "POST"]`, validate credentials, set `session['user_id']` and `session['user_name']` on success, redirect to `landing`; replace the `/logout` stub to clear the session (`session.clear()`) and redirect to `landing`
- `templates/login.html` — re-populate `email` field on validation failure
- `templates/base.html` — conditional nav based on session state

## Files to create
None.

## New dependencies
No new dependencies. Flask's built-in `session` (via `flask.session`) is part of Flask, already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (already satisfied by the existing `get_user_by_email()`)
- Passwords verified with werkzeug (`check_password_hash`) — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py` only — no inline SQL in `app.py`
- `app.secret_key` must be set (required for Flask sessions to work) — read from an environment variable with a hardcoded local-dev fallback, and flag in the summary that a real deployment needs a proper secret
- On invalid email or wrong password, show one generic error (e.g. "Invalid email or password.") — do not reveal whether the email exists, to avoid user enumeration
- Use `url_for()` for every redirect and link — never hardcode `/login`, `/logout`, or `/`
- Do not touch the stub routes still out of scope (`/profile`, `/expenses/...`)
- Do not implement any route-protection/`@login_required` decorator beyond `/logout` itself — that belongs to later steps that add protected pages

## Definition of done
- [ ] Submitting the login form with a registered user's correct email/password redirects to `/` and starts a session
- [ ] After a successful login, the nav bar shows the logged-in user's name and a "Log out" link instead of "Sign in" / "Get started"
- [ ] Submitting the login form with a wrong password or an email that doesn't exist re-renders `login.html` with a generic "Invalid email or password." error and preserves the entered email
- [ ] Visiting `/logout` while logged in clears the session and redirects to `/`, after which the nav reverts to "Sign in" / "Get started"
- [ ] Visiting `/logout` while not logged in does not error — it redirects to `/` cleanly
- [ ] `GET /login` still renders the form normally with no errors
- [ ] App still starts cleanly on port 5001 with no errors
