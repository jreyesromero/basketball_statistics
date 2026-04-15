# Local monitoring (Grafana + Loki + Promtail)

This folder runs a small **observability stack in Docker** that reads JSON Lines from the project’s **`data/logs/`** directory (for example `app.jsonl` and rotated `app.jsonl.*` files from `RotatingFileHandler`).

**Grafana** and **Loki** use official images. **Promtail** is a thin image built from **`docker/promtail.Dockerfile`**, which copies **`promtail/config.yml`** into the container so the config does not rely on a host bind mount (some Colima setups showed an empty `/etc/promtail` when bind-mounting the folder). After editing `promtail/config.yml`, rebuild: **`docker compose build promtail`** then **`docker compose up -d`**.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) v2
- Log files on the host under **`../data/logs/`** (relative to this folder), e.g. from `./bin/run.sh` with `BASKET_LOG_FILE` pointing at `data/logs/app.jsonl`

## Quick start

1. **From the repository root**, ensure the app can write logs (optional but typical for local dev):

   ```bash
   ./bin/run.sh
   ```

   That sets `BASKET_LOG_FILE` to `data/logs/app.jsonl` unless you already exported something else.

2. **Start the stack** (Compose resolves `../data/logs` relative to this directory):

   ```bash
   cd monitoring
   docker compose up -d
   ```

3. **Open Grafana**: [http://127.0.0.1:3000](http://127.0.0.1:3000)

   - Default login: **`admin` / `admin`** (unless you set `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` in a `.env` file in `monitoring/` — see `env.example`).
   - Change the password when prompted on first login, or set env vars before `up` for non-interactive use.

4. **Loki** is already added as the default datasource. Use **Explore** (compass icon) → query **Loki**, or open the dashboard **“Basketball logs”** (logs panel + simple rate by `event`).

## Example LogQL queries

Your app emits one JSON object per line (`ts`, `event`, `request_id`, …). After Promtail’s pipeline, `event` is also a Loki label.

```logql
{job="basketball"}
```

```logql
{job="basketball"} | json
```

```logql
{job="basketball", event="http_request"} | json | line_format "{{.method}} {{.path_template}} {{.status}}"
```

## Ports

| Service  | Port | URL                    |
|----------|------|------------------------|
| Grafana  | 3000 | http://127.0.0.1:3000  |
| Loki API | 3100 | http://127.0.0.1:3100  |

Promtail listens on **9080** inside the compose network only (not published by default).

## Paths and rotation

- **Host path**: `../data/logs` is mounted read-only at **`/var/log/basketball`** in Promtail.
- **Glob**: `*.jsonl*` matches `app.jsonl` and Python’s rotated `app.jsonl.1`, etc.

If you add other `.jsonl` files under `data/logs/`, they are picked up automatically.

## Stop and reset

```bash
cd monitoring
docker compose down
```

Remove stored Loki/Grafana data (fresh start):

```bash
docker compose down -v
```

## Security notes

- Default **admin** credentials are for **local development only**. Use a strong password (`.env`) or OIDC if you expose Grafana beyond localhost.
- Do not commit real passwords; `.env` is listed in the parent `.gitignore` patterns if you add one locally.

## Troubleshooting

- **No logs in Grafana**: Confirm files exist under `data/logs/` and contain lines. Generate traffic against the app, then refresh Explore.
- **Permission denied**: Ensure the log files are readable by Docker (on Linux, UID inside the container must be able to read the bind-mounted directory).
- **Compose path errors**: Always run `docker compose` from **`monitoring/`** so `../data/logs` points at the repo’s `data/logs`.
- **Empty `data/logs` mount in the container** (Promtail sees no files): set **`BASKET_DATA_LOGS_HOST_PATH`** in `monitoring/.env` to the **absolute** path of your repo’s `data/logs` directory (see `env.example`), then `docker compose up -d --force-recreate promtail`.

## Image versions

Pinned in `docker-compose.yml` (Grafana **11.3.1**, Loki **2.9.8**, Promtail **2.9.8**). Bump tags together when you upgrade; check Loki/Promtail compatibility in Grafana’s release notes.
