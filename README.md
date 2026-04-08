# Basketball statistics

A small web application for managing **basketball players** and **clubs** in a local SQLite database. It serves **HTML pages** for day-to-day use and optional **JSON APIs** for scripts or integrations. **Sign-in** protects the web UI; **HTTP Basic authentication** protects the JSON endpoints.

## Features

- **Players:** add, list, and remove players (name, surname, date of birth, optional address). Date of birth cannot be in the future.
- **Clubs:** add, list, and remove clubs (name, foundation date, optional address). Foundation date cannot be in the future.
- **Accounts:** register (non-admin users), sign in with email and password, session cookies (Argon2 password hashing).
- **First administrator:** if the database has **no users**, the app sends you to a **one-time bootstrap** screen to create the first admin account.
- **Administration:** users with `is_admin` can open **User administration** (`/admin/users`) to create users, toggle active/admin flags, and delete users (with safeguards for the last admin).
- **JSON API:** `GET /api/players` and `GET /api/clubs` return lists as JSON when valid **HTTP Basic** credentials are supplied (see [Environment variables](#environment-variables)).

## Tech stack

| Area | Technology |
|------|------------|
| Language | Python 3 |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI server | [Uvicorn](https://www.uvicorn.org/) |
| Templates | [Jinja2](https://jinja.palletsprojects.com/) |
| Database | [SQLite](https://www.sqlite.org/) (file: `data/basket.sqlite`) |
| Password hashing | [Argon2](https://github.com/hynek/argon2-cffi) (`argon2-cffi`) |
| Signed sessions | [Starlette](https://www.starlette.io/) session middleware + [itsdangerous](https://itsdangerous.palletsprojects.com/) |

Forms use `python-multipart`. Styling is plain **CSS** under `src/static/`.

## Project layout

```
basketball_statistics/
├── bin/run.sh           # Creates venv if needed, installs deps, starts Uvicorn
├── schema.sql           # Canonical SQL schema (also applied on first DB create)
├── data/basket.sqlite   # SQLite file (created at runtime; often gitignored)
├── requirements.txt
└── src/
    ├── main.py          # App factory, HTML routes, DB bootstrap migrations
    ├── db_paths.py      # Paths to DB and schema
    ├── queries.py       # Read-only player/club queries
    ├── users_repo.py    # User CRUD helpers
    ├── passwords.py     # Argon2 helpers
    ├── middleware_auth.py
    ├── admin_routes.py  # /admin/* user management
    ├── api/             # JSON routers + HTTP Basic dependency
    ├── templates/       # Jinja HTML
    └── static/          # CSS
```

## How to run

From the **repository root**:

```bash
./bin/run.sh
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The script creates `.venv` if missing, installs `requirements.txt`, and starts Uvicorn with reload.

If `BASKET_SESSION_SECRET` is not set, the script generates a **random secret for that run** (sessions invalid after restart). For a stable secret across restarts, set it yourself (see below).

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BASKET_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `BASKET_SESSION_SECRET` | **Required** (min 32 characters) for signing session cookies. `bin/run.sh` generates one if unset. |
| `BASKET_API_BASIC_USER` | Username for `GET /api/players` and `GET /api/clubs`. |
| `BASKET_API_BASIC_PASSWORD` | Password for those endpoints. If unset or empty, the API returns **503** until both are set. |

See `.env.example` for placeholders. Example API call:

```bash
curl -s -u 'myuser:mysecret' http://127.0.0.1:8000/api/players
```

## How the app flow works

1. **Startup:** Ensures `data/` exists, creates `basket.sqlite` from `schema.sql` if missing, and runs lightweight **migrations** (for example adding the `club` table or `users.is_admin` on older databases).
2. **Browser requests:** Most paths require a **signed session** with an **active** user. Exceptions include `/login`, `/register`, `/bootstrap`, `/static/*`, and `/api/*`.
3. **Empty user table:** Visiting sign-in redirects to **`/bootstrap`** once, to create the **first administrator**. Self-service **`/register`** always creates **non-admin** users.
4. **Admins:** Users with `is_admin = 1` see **User administration** on the home page and can use **`/admin/users`**.
5. **JSON API:** Separate from the session; uses **HTTP Basic** and the same SQLite data via `src/queries.py`.

Interactive API docs (when the server runs): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## SQLite quick reference

Run these from the **repository root** so `data/basket.sqlite` resolves correctly.

### List users (ids, emails, active flag, admin flag)

```bash
sqlite3 data/basket.sqlite "SELECT user_id, email, is_active, is_admin FROM users;"
```

- `is_active`: `1` = can sign in, `0` = disabled.
- `is_admin`: `1` = can access `/admin/users`, `0` = normal user.

### Promote an account to administrator

Replace the email with yours (stored lowercase):

```bash
sqlite3 data/basket.sqlite "UPDATE users SET is_admin = 1 WHERE email = 'you@example.com';"
```

Useful if you had users **before** the admin feature existed (migration defaults `is_admin` to `0` for everyone). After changing the database, **sign out and sign in again** so the session picks up the new flags.

### List players

```bash
sqlite3 data/basket.sqlite "SELECT player_id, surname, name, date_of_birth FROM player;"
```

### List clubs

```bash
sqlite3 data/basket.sqlite "SELECT club_id, name, foundation_date FROM club;"
```

### Open an interactive SQLite shell

```bash
sqlite3 data/basket.sqlite
```

Then run SQL (end with `;`), and type `.quit` to exit.

### Recreate an empty database from the schema file

**Warning:** this deletes existing data.

```bash
mkdir -p data
sqlite3 data/basket.sqlite < schema.sql
```

After that, start the app and use **`/bootstrap`** when the user table is empty.

## License

Use and modify for your own purposes; add a license file if you publish the project.
