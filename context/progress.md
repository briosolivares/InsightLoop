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

- [ ] **Step 3: Interview page, Realtime session token, and live AI interview**

- [ ] **Step 4: Interview completion, post-processing, and structured output**

- [ ] **Step 5: Insights Q&A panel**

---

## Session Notes

- Switched from Node.js/Express to Python/FastAPI during Step 1
- Virtual environment at `.venv/` — run with `source .venv/bin/activate && python main.py`
- ngrok URL: `https://jonathon-palaeoentomological-bev.ngrok-free.dev` (set as `BASE_URL` in `.env`)
- Design doc and implementation plan updated to reflect FastAPI stack
