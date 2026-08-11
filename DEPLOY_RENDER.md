# Deploy Nexus Analytics to Render

FastAPI serves both the static frontend and the API. The compatibility entrypoint remains `ai_service:app`.

## Blueprint

1. Push the repository to GitHub.
2. In Render choose **New + → Blueprint**.
3. Select the repository and apply `render.yaml`.
4. Confirm the health endpoint at `/health` and API documentation at `/docs`.

## Manual Web Service

- Runtime: `Python`
- Build command: `pip install --no-cache-dir -r requirements.txt`
- Start command: `uvicorn ai_service:app --host 0.0.0.0 --port $PORT`

Environment configuration:

- `PYTHON_VERSION=3.11.9`
- `APP_ENV=staging` for a staging deployment or `production` for production
- `DATABASE_PATH=./sales.db` for the current SQLite deployment
- `SEED_DEMO_DATA=false`
- `CORS_ORIGINS=https://your-production-domain.example` is mandatory when `APP_ENV=production`
- `UPLOAD_DIR=./data/uploads`
- `MAX_UPLOAD_BYTES=10485760`
- `MAX_IMPORT_ROWS=100000`
- `MAX_IMPORT_COLUMNS=100`

## Data persistence warning

Render's default filesystem is ephemeral. A production deployment must put both
`DATABASE_PATH` and `UPLOAD_DIR` on a persistent disk, or migrate metadata to a
managed database and files to durable object storage. Local SQLite and upload
storage are suitable for the current demo/staging workflow only.

No AI provider or external analytics provider is configured in Phase 1.
