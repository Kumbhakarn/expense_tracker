# Spec: Registration

## Overview
This step implements the actual account-creation logic behind the existing `/register` page. `GET /register` currently only renders a static form (`register.html`); this step wires up form submission so a visitor can create a real account backed by the `users` table established in Step 1. This is the first authentication step in the Spendly roadmap and unblocks Step 3 (login/logout) and everything downstream that requires a logged-in user.

## Depends on
- Step 1 — Database Setup (`.claude/specs/01.database-setup.md`): requires `get_db()`, `init_db()`, and the `users` table with `name`, `email`, `password_hash` columns to already exist.

## Routes
- `GET /register` — renders the registration form — public (already implemented, unchanged)
- `POST /register` — validates submitted form data, creates a new user with a hashed password, and redirects to `/login` on success; re-renders `register.html` with an error message on failure — public

## Database changes
No schema changes. The `users` table (from `database/db.py`) already has the required columns (`name`, `email` UNIQUE, `password_hash`). This step adds a new function to `database/db.py`:
- `create_user(name, email, password)` — hashes the password with `werkzeug.security.generate_password_hash` and inserts a new row into `users` using a parameterized query; lets the caller (route) handle the `sqlite3.IntegrityError` raised on duplicate email.
- `get_user_by_email(email)` — parameterized `SELECT` used to pre-check for an existing email before insert, returning the row or `None`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — add `{% if error %}` block usage already present (keep as-is); ensure submitted `name`/`email` values are re-populated in the inputs (`value="{{ name or '' }}"`, etc.) after a failed submission so the user doesn't retype everything.

## Files to change
- `app.py` — change `/register` route to accept `["GET", "POST"]`, handle form validation, call `database/db.py` helpers, redirect to `/login` on success
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — re-populate `name`/`email` fields on validation failure

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py` only — no inline SQL in `app.py`
- Validate in the route: `name`, `email`, `password` all required and non-empty; email must contain `@`; password minimum 8 characters (matches the placeholder text already in `register.html`)
- On duplicate email, show a friendly error (e.g. "An account with that email already exists.") rather than a raw database error
- Use `url_for()` for the redirect to login — never hardcode `/login`
- Do not touch the stub routes (`/logout`, `/profile`, `/expenses/...`) — they remain out of scope for this step

## Definition of done
- [ ] Submitting the register form with a new name/email/password (≥8 chars) creates a row in the `users` table with a hashed password (not plaintext)
- [ ] After successful registration, the browser is redirected to `/login`
- [ ] Submitting with an email that already exists in `users` re-renders `register.html` with an error message and does not create a duplicate row
- [ ] Submitting with a missing field or a password under 8 characters re-renders `register.html` with an appropriate error and preserves the previously entered name/email
- [ ] `GET /register` still renders the form normally with no errors
- [ ] No plaintext passwords appear anywhere in the database
- [ ] App still starts cleanly on port 5001 with no errors
