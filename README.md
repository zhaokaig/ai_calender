# ai_calender

A voice-first AI calendar built for a two-day Hackathon demo.

## Current Scope

The project now includes:

- Flask backend with register/login and calendar event CRUD APIs;
- React frontend for testing authentication and event workflows;
- a placeholder chat panel for future LLM and voice input flows.

See `backend/ai_calender_backend_prd.md` for the full MVP plan.

## Backend Setup

```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/flask --app app.main init-db
../.venv/bin/flask --app app.main run
```

The backend starts at:

```text
http://127.0.0.1:5000
```

## Health Check

```bash
curl http://127.0.0.1:5000/api/health
```

Expected response:

```json
{
  "environment": "development",
  "service": "ai-calender",
  "status": "ok"
}
```

## Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The React frontend starts at:

```text
http://127.0.0.1:5173
```

During local development, Vite proxies `/api` requests to:

```text
http://127.0.0.1:5000
```

To point the frontend at a different backend URL, set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:5000 npm run dev
```

## Frontend Test Flow

1. Start the backend and frontend.
2. Open `http://127.0.0.1:5173`.
3. Register a user with a password of at least 6 characters.
4. Add an event from the main calendar page.
5. Click a date to view its events in the right panel.
6. Click an event to edit or delete it.
7. Use logout, then log back in with the same account.
8. Click the short recording, long recording, or keyboard buttons to verify the placeholder chat UI.

## Frontend Build

```bash
cd frontend
npm run build
```

## Docker Compose Deployment

Build the production-style Docker images locally:

```bash
docker compose build
```

Initialize the SQLite database in the persistent Docker volume:

```bash
docker compose run --rm backend flask --app app.main init-db
```

Start the backend and Nginx services:

```bash
docker compose up -d
```

The app is available at:

```text
http://127.0.0.1:8080
```

The health check is available at:

```bash
curl http://127.0.0.1:8080/api/health
```

Useful operational commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f nginx
docker compose restart
docker compose down
```

For server deployment, create `backend/.env` on the server with production values:

```env
APP_ENV=production
SECRET_KEY=replace-with-a-strong-random-secret
DATABASE_PATH=instance/ai_calender.sqlite
DASHSCOPE_API_KEY=replace-with-your-dashscope-api-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ASR_MODEL=qwen3-asr-flash-2026-02-10
AGENT_MODEL=qwen-plus
AGENT_TEMPERATURE=0
LOG_LEVEL=INFO
LOG_FILE_PATH=instance/ai_calender.log
```

The default Compose port mapping is `8080:80` for local testing.

On a server, use the server override so the frontend is available directly on port 80:

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml up -d
```

Then open:

```text
http://your-server-ip/
```

If you bind a domain name to the server, open:

```text
http://your-domain.com/
```

## Voice Command API

PR 3 adds a text-in, action-out agent endpoint. The frontend should send text produced by browser speech recognition or by the backend ASR endpoint.

Configuration lives in `backend/.env`, so you do not need to export variables manually. Replace the placeholder key before running ASR or model-backed parsing:

```env
DASHSCOPE_API_KEY=your-bailian-api-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ASR_MODEL=qwen3-asr-flash-2026-02-10
AGENT_MODEL=qwen-plus
```

The backend uses Alibaba Cloud Model Studio / DashScope OpenAI-compatible APIs, LangChain for model calls, and LangGraph for agent orchestration.
If no valid `DASHSCOPE_API_KEY` is configured, `/api/voice-command` uses a small rule-based fallback for the demo script. `/api/transcriptions` requires `DASHSCOPE_API_KEY`.

Example flow:

```bash
curl -X POST http://127.0.0.1:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"password123"}'
```

Then call:

```bash
curl -X POST http://127.0.0.1:5000/api/voice-command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"text":"明天下午三点和 Alex 开会","timezone":"Asia/Shanghai"}'
```

To transcribe audio with Qwen ASR:

```bash
curl -X POST http://127.0.0.1:5000/api/transcriptions \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/audio.webm"
```

## MVP Demo Goal

The final Hackathon demo should support:

- creating calendar events by voice;
- querying events by voice;
- updating events by voice;
- deleting events by voice;
- using text input as a fallback when voice recognition is unreliable.
