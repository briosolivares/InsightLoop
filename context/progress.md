# Insight Loop — Progress Tracker

## Implementation Steps

- [x] **Step 1: Project scaffold, config API, and data layer**
  - FastAPI + Uvicorn server (`main.py`)
  - `requirements.txt` + `.venv` set up
  - `GET /POST /api/config` with flat-file persistence (`data/config.json`)
  - Placeholder `dashboard.html` and `interview.html` served
  - `.env`, `.env.example`, `.gitignore` configured
  - Committed ✓

- [x] **Step 2: Interview CRUD API and founder dashboard shell**
  - `POST /api/interviews` — creates interview, generates UUID + ngrok URL, saves `meta.json`
  - `GET /api/interviews` — lists all interviews sorted by `created_at` descending
  - `GET /api/interviews/:id` — returns meta; includes `report` + `extracted` if completed
  - `POST /api/interviews` with missing `name` → 422 (Pydantic validation)
  - Full 3-panel dashboard: Setup (ICP/hypotheses save), Interviews (create, list, copy link, view report), Insights (chat placeholder)
  - 5-second polling to keep status badges live
  - Committed ✓

- [x] **Step 3: Interview page, Realtime session token, and live AI interview**
  - `POST /api/interviews/:id/session-token` — builds system prompt from ICP + hypotheses, creates OpenAI Realtime session, updates status to `in_progress`, returns ephemeral `client_secret`
  - `POST /api/interviews/:id/complete` — stub: saves `transcript.json`, marks status `completed` (post-processing added in Step 4)
  - `public/interview.html` — 4-state UI (waiting-for-mic → connecting → in_progress → completed)
  - WebRTC connects browser directly to OpenAI Realtime API using ephemeral token
  - Accumulates transcript from `response.audio_transcript.done` + `conversation.item.input_audio_transcription.completed` events
  - Detects `finish_interview` tool call from AI via `response.done` event to trigger `/complete`
  - AI given `finish_interview` function tool + full system prompt with ICP + hypotheses

- [x] **Step 4: Interview completion, post-processing, and structured output**
  - `POST /complete` enhanced: saves transcript → GPT-4o extraction → GPT-4o report → marks completed
  - `prompts/extract_insights.txt` — structured extraction prompt (pain points, workflows, tools, hypothesis assessment)
  - `prompts/generate_report.txt` — markdown report prompt
  - `fill_template()` helper replaces `.format()` to avoid Python treating JSON braces in templates as placeholders
  - Both `extracted.json` and `report.md` verified against real GPT-4o output
  - Dashboard "View Report" button already wired — surfaces report on completion

- [x] **Step 5: Insights Q&A panel**
  - `POST /api/insights` — loads all completed interviews' `extracted.json`, passes structured context to GPT-4o, returns answer
  - `prompts/insights_qa.txt` — prompt template with `{interview_count}`, `{context}`, `{question}` placeholders
  - `run_insights()` in `agent.py` — formats extracted data per interview, calls GPT-4o
  - `InsightsPayload` Pydantic model in `main.py`
  - Dashboard chat input already wired — sends question, renders answer inline
  - Chat input auto-enables when at least one completed interview exists

---

## Session Notes

- Switched from Node.js/Express to Python/FastAPI during Step 1
- Virtual environment at `.venv/` — run with `source .venv/bin/activate && python main.py`
- ngrok URL: `https://jonathon-palaeoentomological-bev.ngrok-free.dev` (set as `BASE_URL` in `.env`)
- Design doc and implementation plan updated to reflect FastAPI stack
- `main.py` refactored into `storage.py` (file I/O), `agent.py` (all OpenAI logic), `main.py` (routes only)
- `load_dotenv()` called in both `main.py` and `agent.py` — agent.py initializes the OpenAI client at import time
