# 16 Lab — backend (core)

FastAPI service served under `/api` on the same origin as the static front end.
This is the core slice: gateway health, live bar decode, and deterministic scoring.
Musixmatch search/lyrics, the upload pipeline, and the scores endpoints layer on after.

## Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put GATEWAY_KEY in .env
uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET  | `/api/health` | liveness + flags |
| GET  | `/api/llm/ping` | confirms the gateway routes + which model answers |
| POST | `/api/decode/bar` | body `{ text, context? }` → `{ meaning, wordplay, references[], cultural }` |
| GET  | `/api/track/{id}/score` | `{ score, metrics[], rhymes[] }` (deterministic, no LLM) |

## How keys work

- **All config is env-only.** Nothing is hardcoded; nothing is committed. See `.env.example`.
- The **LLM gateway** is used live whenever `GATEWAY_KEY` is set — so decode works
  before any other key arrives. With no key, `/api/decode/bar` returns a clearly
  labelled mock and `/api/llm/ping` returns 503.
- `MOCK_MODE=true` makes the data services (Musixmatch / Scribe / LALAL) return
  canned data. Scoring is **always** computed for real.

## Compliance

- **Never persist Musixmatch lyric content** — live fetch at display time only.
  Our own outputs (decodes, scores, transcripts) may be cached.

## Deploy (VM)

Run behind nginx as a reverse proxy so the FE and `/api` share one origin:

```
location /api/ { proxy_pass http://127.0.0.1:8000/api/; }
```

Use a process manager (systemd/gunicorn+uvicorn workers). Only expose 80/443 via
nginx; keep the uvicorn port (8000) bound to localhost.
