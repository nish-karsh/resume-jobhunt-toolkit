# Hosting & Access Options

How to run the app and, if you want, reach it beyond your desk. Because the toolkit handles your resume, contacts, and an API key, **local-first is strongly recommended**.

---

## Option A - Local on your Windows PC (recommended)

Just run `run.bat`. The app serves at `http://localhost:8501`.

- **Pros:** completely private (resume, tracker, and `.env` never leave your PC), free, no setup beyond the install.
- **Cons:** only reachable on that PC.
- **Best for:** essentially all daily job-hunting.

**Quality-of-life tweaks:**
- **Desktop shortcut:** right-click `run.bat` -> *Send to* -> *Desktop (create shortcut)*.
- **Same LAN (your own phone/laptop at home):** start with `streamlit run app.py --server.address 0.0.0.0`, then browse to `http://<your-pc-ip>:8501` from another device on the same Wi-Fi. Only do this on trusted networks; there is no authentication.

---

## Option B - Temporary tunnel for phone access

Run the app locally, then expose it briefly with a tunnel when you need it on the go.

**cloudflared (no account needed for quick tunnels):**
```powershell
# 1) start the app in one terminal
streamlit run app.py
# 2) in another terminal, tunnel it
cloudflared tunnel --url http://localhost:8501
```
cloudflared prints a temporary public `https://...trycloudflare.com` URL. (Alternatives: `ngrok http 8501`, or Tailscale for a private mesh.)

- **Pros:** reach the app from anywhere while the tunnel runs.
- **Cons:** the app is publicly reachable **with no login** while the tunnel is up - anyone with the URL can use it. Your PC must stay on.
- **Do:** stop the tunnel (`Ctrl+C`) as soon as you're done. Don't share the URL.

---

## Option C - Cloud hosting (always-on, private)

Deploy so it's reachable anywhere without your PC. The app has a dedicated **cloud mode**
(`mode: cloud`): password-gated, portable HTML→PDF, apply = open-link only.

**Recommended (free): Streamlit Community Cloud.** Push to a **private** GitHub repo and deploy
`app.py` at [share.streamlit.io](https://share.streamlit.io). It's free, allows one private app,
installs `requirements.txt`, and has a secrets manager. PDFs use the pure-Python **fpdf2** engine.

> Hugging Face **Docker** Spaces are no longer free (they now need a paid PRO plan; only static
> Spaces are free), so they're no longer the recommended free option.

**Alternatives (Docker, full WeasyPrint PDFs):** **Render** free web service (builds from the
`Dockerfile`; ~50s cold start after idle) or **Google Cloud Run** (generous free tier, scales to
zero, needs a Google account with a billing card on file).

- Always set an **`app_password`** secret and keep the repo **private**.
- On Streamlit Community Cloud, switch to cloud mode by adding `SETTINGS__MODE="cloud"` to the
  app's secrets. Its disk is **ephemeral** (resets on reboot), so use the in-app
  **Backup / restore tracker** control to save/restore `jobhunt.db`.
- On Render/Cloud Run, set `DATA_DIR` to a mounted volume to persist `data/`.

Full, copy-paste steps (repo, secrets TOML, GitHub push) are in
**[DEPLOY_CLOUD.md](DEPLOY_CLOUD.md)**.

---

## Recommendation

| Need | Use |
|------|-----|
| Everyday job hunting (full features) | **A - local `run.bat`** (`mode: local`) |
| Occasional phone access to your local app | **B - cloudflared tunnel**, stopped when done |
| Always-on, PC-free, private, free | **C - Streamlit Community Cloud** (see [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md)) |

For maximum privacy, **stick with Option A**. For convenience, **C** with a private repo +
`app_password` keeps access controlled for free. See the privacy section in the root
[README.md](../README.md).
