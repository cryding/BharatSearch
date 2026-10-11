# BharatSearch 🇮🇳

**An open-source, India-inspired search and browsing project.** MIT licensed.

BharatSearch is being built as a website + native Android client backed by an independent, self-hostable crawler and search index. It is an early-stage project, not a complete replacement for Google or Chrome.

## Current scope

- Website search interface with configurable API URL.
- Python API and SQLite FTS5 search index.
- Bounded, operator-triggered crawler with robots.txt checks, crawl delay, page/depth limits, and a private-network URL guard.
- Native Android app scaffold with search UI.
- Free GitHub Actions checks/builds. No paid APIs or credits are required for local development.

## Architecture

```
Website / Android app
        | HTTPS in production
        v
FastAPI search API ---- SQLite FTS5 index
        ^                       ^
        |                       |
   bounded crawler -------------+
```

## Repository layout

- `backend/` — API, index and crawler
- `web/` — static search website
- `android/` — native Android application (Kotlin + Jetpack Compose)
- `.github/workflows/` — free-tier CI workflows

## Run locally

Requirements: Python 3.11+.

```bash
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `web/index.html` in a browser and set the API URL to `http://127.0.0.1:8000`, or serve the web directory with `python -m http.server 8080` from the repository root.

API docs: `http://127.0.0.1:8000/docs`.

## Add pages to the index

Crawling is deliberately manual and bounded; this project does not run a public, unrestricted crawler by default.

```bash
curl -X POST http://127.0.0.1:8000/api/crawl \
  -H 'Content-Type: application/json' \
  -d '{"seed_urls":["https://example.com/"],"max_pages":10,"max_depth":1}'
```

Only crawl sites you are authorized to access. Respect robots.txt, site terms, copyright, and server load. Do not use this as a denial-of-service tool. Publicly exposing the crawl endpoint without authentication/rate limits is not recommended.

## Configuration

- `BHARATSEARCH_DB`: SQLite database path (default `bharatsearch.db`)
- `BHARATSEARCH_ALLOWED_ORIGINS`: comma-separated CORS origins (default localhost development origins)
- `BHARATSEARCH_USER_AGENT`: crawler user-agent string

## Android

Open `android/` in Android Studio with a compatible Android SDK installed. The app defaults to a local Android-emulator development API URL. Set `API_BASE_URL` in `android/app/build.gradle.kts` to your deployed HTTPS API for production. Do not ship a public release pointing to localhost.

## Important limitations

- A fresh index contains only pages explicitly crawled. There is no global web index yet.
- Search quality depends on indexed documents; ranking is a basic SQLite full-text relevance ranking.
- No production API, APK release, hosted website, domain, or public crawler deployment is claimed by this initial implementation.
- Free-tier quotas and availability can change. The project uses open-source software and does not require paid APIs.

## License

MIT — see [LICENSE](LICENSE).
