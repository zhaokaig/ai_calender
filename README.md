# ai_calender

A voice-first AI calendar built for a two-day Hackathon demo.

## Current Scope

PR 1 sets up the backend foundation:

- Flask application scaffold;
- basic configuration;
- health check endpoint;
- startup instructions.

See `backend/ai_calender_backend_prd.md` for the full MVP plan.

## Backend Setup

```bash
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
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

## MVP Demo Goal

The final Hackathon demo should support:

- creating calendar events by voice;
- querying events by voice;
- updating events by voice;
- deleting events by voice;
- using text input as a fallback when voice recognition is unreliable.
