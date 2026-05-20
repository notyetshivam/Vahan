# Deploying Vahan Auto-Analytics Hub

The repo is git-initialized and ready. Two halves to deploy:

| Part         | Where                          | Cost | Time   |
|--------------|--------------------------------|------|--------|
| Dashboard    | **Streamlit Community Cloud**  | Free | ~3 min |
| API (for bot)| **Render** (web service)       | Free | ~5 min |

You only need the API once Phase-2 bot work starts. Do the dashboard first.

---

## Part 1 — Streamlit Community Cloud (dashboard)

### 1. Push to GitHub

1. Go to https://github.com/new
2. Create a repo (any name, e.g. `vahan-dashboard`). **Don't** init with README — your local repo already has one.
3. Copy the two `git remote add` + `git push` commands GitHub shows. They look like:

   ```powershell
   cd Z:\Vahan
   git remote add origin https://github.com/<YOU>/vahan-dashboard.git
   git push -u origin main
   ```

   On first push you'll be prompted for GitHub credentials (use a Personal Access Token, not your password — make one at https://github.com/settings/tokens with the `repo` scope).

### 2. Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io  → sign in with GitHub.
2. Click **New app**.
3. Fill the form:
   - **Repository:** `<YOU>/vahan-dashboard`
   - **Branch:** `main`
   - **Main file path:** `app/streamlit_app.py`
   - **Python version:** 3.11 (already pinned in `runtime.txt`)
4. Click **Deploy**.

First boot takes ~2 min (installs deps, ingests the 38 xlsx files on first run via the `_bootstrap()` hook). You'll get a public URL like `https://vahan-dashboard-<hash>.streamlit.app`.

### 3. Updating later

Just `git push`. Streamlit Cloud auto-redeploys.

To refresh the YTD data on the deployed app: drop new xlsx files in `data/ytd/` locally, commit, push — or expose an admin button that calls `ingest.refresh_ytd()`.

---

## Part 2 — Render (FastAPI, for the bot)

Skip until you start the Telegram bot.

1. Go to https://render.com → sign in with GitHub.
2. **New → Web Service** → pick the same repo.
3. Fill:
   - **Environment:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. Deploy. You'll get `https://vahan-api-<hash>.onrender.com` — pass that URL to the bot via env var.

Add a **persistent disk** (1 GB free) mounted at `/opt/render/project/src/data` so the DuckDB file and parquet history survive restarts.

---

## Troubleshooting

- **Build fails on Streamlit Cloud → `duckdb` install error**: that means it picked Python 3.13+. Confirm `runtime.txt` says `python-3.11` and re-deploy.
- **App boots but shows "No data ingested yet"**: open the sidebar, click **🔁 Re-ingest YTD folder**. The bootstrap hook should handle it but the manual button is the failsafe.
- **App is too slow on first load**: free Streamlit Cloud containers sleep after inactivity; first request after sleep takes ~30s to wake.

---

## Alternative: Hugging Face Spaces (no GitHub required)

If you'd rather skip GitHub entirely:

1. Make an account at https://huggingface.co
2. Click **New Space** → SDK: **Streamlit**.
3. Use the web UI to drag-drop all repo files (or `git push` to the HF remote they give you).
4. App URL: `https://huggingface.co/spaces/<YOU>/vahan-dashboard`

Same `requirements.txt` works as-is.
