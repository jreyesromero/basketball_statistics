# Basketball statistics

A small web application for managing **basketball players** and **clubs** in a local SQLite database. It serves **HTML pages** for day-to-day use and optional **JSON APIs** for scripts or integrations. **Sign-in** protects the web UI; **HTTP Basic authentication** protects the JSON endpoints.

## Features

- **Players:** add, list, and remove players (name, surname, date of birth, optional address). Date of birth cannot be in the future.
- **Clubs:** add, list, and remove clubs (name, foundation date, optional address). Foundation date cannot be in the future.
- **Seasons and rosters:** define seasons, attach clubs as teams for a season, assign players with optional jersey numbers (`/seasons`, …). A player can appear on only one team per season.
- **Accounts:** register (non-admin users), sign in with email and password, session cookies (Argon2 password hashing).
- **Password reset:** forgot-password flow with time-limited tokens. With **`BASKET_SMTP_HOST`** set, reset links are sent by email; otherwise the link is printed to **stderr** (handy for local development—watch the terminal where Uvicorn runs).
- **First administrator:** if the database has **no users**, the app sends you to a **one-time bootstrap** screen to create the first admin account.
- **Administration:** users with `is_admin` can open **User administration** (`/admin/users`) to create users, toggle active/admin flags, and delete users (with safeguards for the last admin). Admins can view an **audit log** of roster-related changes (`/admin/audit-log`).
- **JSON API:** `GET /api/players` and `GET /api/clubs` return lists as JSON when valid **HTTP Basic** credentials are supplied (see [Environment variables](#environment-variables)).
- **Structured logging:** JSON log lines to stdout and, by default when using `bin/run.sh`, to a rotating file under `data/logs/` (suitable for local **Grafana + Loki** via `monitoring/`).
- **Automated tests:** [pytest](https://pytest.org/) suite under `tests/` (passwords, users, password-reset repo, queries, admin validation, roster repo, management routes, and more).

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
├── bin/run.sh              # Creates venv if needed, installs deps, sets log path, starts Uvicorn (dev)
├── Jenkinsfile             # CI: pytest on branch `development` (Multibranch or equivalent)
├── Jenkinsfile.deploy      # Manual deploy over SSH (rsync + venv + systemd); separate Jenkins job
├── monitoring/             # Optional Docker stack: Grafana + Loki + Promtail (see monitoring/README.md)
├── pytest.ini
├── requirements-dev.txt    # App deps + pytest (CI and local test runs)
├── requirements.txt        # Runtime app dependencies
├── schema.sql              # Canonical SQL schema (also applied on first DB create / migrations)
├── data/
│   ├── basket.sqlite       # Created at runtime (gitignored)
│   └── logs/               # JSON logs when BASKET_LOG_FILE points here (gitignored except .gitkeep)
├── tests/                  # pytest
└── src/
    ├── main.py             # App factory, auth pages, players/clubs HTML routes
    ├── db_paths.py
    ├── observability.py    # JSON logging, request middleware
    ├── queries.py
    ├── users_repo.py
    ├── passwords.py
    ├── password_reset_repo.py
    ├── password_reset_mail.py
    ├── middleware_auth.py
    ├── admin_routes.py     # /admin/* (users, audit log)
    ├── roster_routes.py    # /seasons*, roster HTML
    ├── roster_repo.py      # Seasons, teams, rosters, audit_log
    ├── api/                # JSON routers + HTTP Basic dependency
    ├── templates/
    └── static/
```

## How to run

From the **repository root**:

```bash
./bin/run.sh
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The script creates `.venv` if missing, installs `requirements.txt`, sets **`BASKET_LOG_FILE`** to `data/logs/app.jsonl` when unset, and starts Uvicorn with **`--reload`** on `127.0.0.1:8000`.

**Session secret:** `src/main.py` refuses to start unless **`BASKET_SESSION_SECRET`** is at least 32 characters. `bin/run.sh` generates one for the current process if the variable is unset (cookies reset when the server restarts). For production, set a stable secret (for example via systemd `EnvironmentFile`).

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BASKET_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export BASKET_LOG_FILE="${PWD}/data/logs/app.jsonl"   # optional; omit to log only to stdout
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

## Unit tests

Tests live in **`tests/`** and are run with **[pytest](https://pytest.org/)**. They use a temporary SQLite database (via `monkeypatch` on `DB_PATH` in the relevant modules) so your real `data/basket.sqlite` is not touched. `tests/conftest.py` sets a dummy `BASKET_SESSION_SECRET` so imports stay safe.

Install **development** dependencies (includes `requirements.txt` and pytest), then run pytest from the **repository root**:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/pytest
```

If you use an activated virtualenv (`source .venv/bin/activate`), you can use `pip install -r requirements-dev.txt` and `pytest` directly. If `pip` is not on your `PATH`, prefer **`python -m pip`** as shown above.

`pytest.ini` sets `testpaths = tests` and `pythonpath = .` so `import src.…` resolves correctly.

## Jenkins (continuous integration)

The repo root **`Jenkinsfile`** defines a **declarative Jenkins pipeline** that:

1. Checks out the repository.
2. On branches **other than** `development`, skips install and tests (informational message only).
3. On the **`development`** branch, creates a virtualenv, installs **`requirements-dev.txt`**, sets `BASKET_SESSION_SECRET` for the build, and runs **`pytest -q`**.

Configure your Jenkins job (for example a **Multibranch Pipeline** pointed at this GitHub repository) so builds run on pushes to **`development`**. GitHub **webhooks** require a URL that GitHub can reach; **localhost** Jenkins is not reachable from the internet unless you use **Poll SCM**, a **tunnel** (e.g. ngrok), or Jenkins hosted on a public URL. Adjust the pipeline’s `when { branch 'development' }` blocks if your job does not set `BRANCH_NAME` (some single-branch jobs).

## Jenkins (manual deploy)

**`Jenkinsfile.deploy`** is intended for a **separate** Pipeline job (for example *Pipeline script from SCM* with **Script Path** `Jenkinsfile.deploy` and **no** automatic triggers). You run it when you choose to deploy.

The pipeline checks out a configurable **git ref** (default `master`), **rsyncs** `src/`, `bin/`, `requirements.txt`, `schema.sql`, and `pytest.ini` to a target host (so a server-local **`data/basket.sqlite`** is not overwritten), then over SSH ensures a `.venv`, runs **`pip install -r requirements.txt`**, and optionally **`sudo systemctl restart`** a named unit.

Prerequisites and parameters (SSH credential id, host, paths, systemd unit name) are documented in comments at the top of **`Jenkinsfile.deploy`**. The app process on the server should be defined in **systemd** for production (stable `BASKET_SESSION_SECRET`, bind address, no `--reload`); `bin/run.sh` remains oriented toward local development.

## Local monitoring (optional)

The **`monitoring/`** directory contains a **Docker Compose** stack (**Grafana**, **Loki**, **Promtail**) that ingests JSON Lines from **`data/logs/`** (same format the app writes when `BASKET_LOG_FILE` is set). See **[monitoring/README.md](monitoring/README.md)** for ports, quick start, and LogQL examples.

## Environment variables

`.env` and `.env.*` are **gitignored**; set variables in your shell, systemd unit, or container. Common choices:

| Variable | Purpose |
|----------|---------|
| `BASKET_SESSION_SECRET` | **Required** (min 32 characters) for signing session cookies. `bin/run.sh` generates one per run if unset. If you start **`uvicorn` directly** without exporting this, the process exits on startup. |
| `BASKET_API_BASIC_USER` | Username for `GET /api/players` and `GET /api/clubs`. |
| `BASKET_API_BASIC_PASSWORD` | Password for those endpoints. If unset or empty, the API returns **503** until both are set. |
| `BASKET_LOG_FILE` | If set to a non-empty path, JSON logs are also appended there (**RotatingFileHandler**). Relative paths are resolved from the project root. Set to empty to disable file logging. |
| `BASKET_LOG_MAX_BYTES` | Max size per log file before rotation (default `5242880`, 5 MiB). |
| `BASKET_LOG_BACKUP_COUNT` | Number of rotated log files to keep (default `5`). |
| `BASKET_SMTP_HOST` | SMTP server for password-reset emails. If unset, the reset link is printed to **stderr** instead of being emailed (see `src/password_reset_mail.py`). |
| `BASKET_SMTP_PORT` | SMTP port (default `587`). |
| `BASKET_SMTP_USER` | SMTP auth user (optional for some servers). |
| `BASKET_SMTP_PASSWORD` | SMTP password. |
| `BASKET_SMTP_FROM` | From address (defaults to `BASKET_SMTP_USER` if unset). |

Example API call:

```bash
curl -s -u 'myuser:mysecret' http://127.0.0.1:8000/api/players
```

## How the app flow works

1. **Startup:** Ensures `data/` exists, creates `basket.sqlite` from `schema.sql` if missing, and runs lightweight **migrations** (for example adding tables or columns present in `schema.sql` but missing in older files).
2. **Browser requests:** Most paths require a **signed session** with an **active** user. Exceptions include `/login`, `/register`, `/bootstrap`, `/forgot-password`, `/reset-password`, `/static/*`, and `/api/*` (plus OpenAPI paths where enabled).
3. **Empty user table:** Visiting sign-in redirects to **`/bootstrap`** once, to create the **first administrator**. Self-service **`/register`** always creates **non-admin** users.
4. **Admins:** Users with `is_admin = 1` see **User administration** on the home page, can use **`/admin/users`**, and can open **`/admin/audit-log`** for roster-related audit entries.
5. **JSON API:** Separate from the session; uses **HTTP Basic** and the same SQLite data via `src/queries.py`.
6. **Seasons:** Signed-in users use **`/seasons`** and related pages to manage seasons, club participation, and rosters (see `src/roster_routes.py`).

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
