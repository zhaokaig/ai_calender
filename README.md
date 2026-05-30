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

## MVP Demo Goal

The final Hackathon demo should support:

- creating calendar events by voice;
- querying events by voice;
- updating events by voice;
- deleting events by voice;
- using text input as a fallback when voice recognition is unreliable.
