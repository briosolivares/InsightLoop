# Insight Loop

An AI-powered market research interview tool for founders. Define your ICP and hypotheses, share a link with a customer, and let an AI voice agent conduct the interview — then get structured insights and a written report automatically.

**Live at:** http://localhost:3000 (or your configured `BASE_URL`)

---

## What It Does

Insight Loop runs a complete research loop from conversation to insight:

1. **Setup** — Define your Ideal Customer Profile and the hypotheses you want to test
2. **Interview** — Share a unique link with a customer; the AI conducts a voice interview in their browser, probing each hypothesis with follow-up questions
3. **Extract** — When the interview ends, GPT-4o extracts structured insights: pain points, workflows, tools mentioned, and hypothesis assessments with supporting quotes
4. **Report** — A human-readable markdown report is generated automatically and viewable in the dashboard
5. **Query** — Ask natural language questions across all completed interviews ("What's the most common pain point?" or "Was H2 confirmed?") and get synthesized answers

---

## Technical Overview

### Architecture

The core design decision is **client-direct WebRTC**: the interviewee's browser connects directly to OpenAI's Realtime API using a short-lived ephemeral token. The backend never handles audio — it only generates the token and receives the finished transcript.

```
Founder's Machine
┌───────────────────────────────────────────────────────┐
│  Founder Dashboard (browser)  ◄──►  FastAPI Backend   │
│                                     (main.py)         │
│                                     ↕ GPT-4o          │
└───────────────────────────────────────────────────────┘

Interviewee (any device, any network):
┌───────────────────────────────────────────────────────────┐
│  Browser opens /interview/:id                             │
│  → POST /api/interviews/:id/session-token  (get token)    │
│  → WebRTC direct ──────────────────────────► OpenAI       │
│                                          gpt-4o-realtime  │
│  On end: POST /api/interviews/:id/complete (transcript)   │
└───────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, FastAPI, Uvicorn |
| Voice interview | OpenAI Realtime API (`gpt-4o-realtime-preview`) via WebRTC |
| Post-processing | OpenAI Chat Completions (`gpt-4o`) |
| Frontend | Vanilla HTML/CSS/JS, marked.js (report rendering) |
| Storage | Flat files — JSON + Markdown (no database) |
| External access | ngrok via `BASE_URL` env var |

### File Layout

```
InsightLoop/
├── main.py               # FastAPI routes
├── agent.py              # All OpenAI logic (Realtime session, extraction, report, insights Q&A)
├── storage.py            # File I/O helpers and path constants
├── prompts/
│   ├── interview_system.txt   # System prompt for the AI interviewer
│   ├── extract_insights.txt   # Extraction prompt → extracted.json
│   ├── generate_report.txt    # Report prompt → report.md
│   └── insights_qa.txt        # Q&A prompt → insights answers
├── public/
│   ├── dashboard.html    # Founder dashboard (3-panel)
│   └── interview.html    # Interviewee page
└── data/
    ├── config.json       # ICP + hypotheses
    └── interviews/
        └── {id}/
            ├── meta.json         # Status, name, notes, URL
            ├── transcript.json   # Raw turn-by-turn transcript
            ├── extracted.json    # Structured insights
            └── report.md         # Human-readable report
```

### Key Flows

**Interview session:**
1. Founder creates an interview → backend generates a UUID and a shareable URL
2. Interviewee opens the URL, grants mic access
3. Browser calls `/session-token` → backend creates an OpenAI Realtime session pre-loaded with the ICP and hypotheses, returns an ephemeral token
4. Browser establishes WebRTC directly with OpenAI; AI conducts the interview
5. AI calls the `finish_interview` tool when done → browser POSTs the full transcript to `/complete`
6. Backend runs two sequential GPT-4o calls: extract insights → generate report → marks `completed`
7. Dashboard polls every 5 seconds and updates the status badge

**Insights Q&A:**
1. Founder types a question in the Insights panel
2. Backend loads `extracted.json` from every completed interview
3. GPT-4o answers with reference to specific interviews where relevant

---

## Setup

**Prerequisites:** Python 3.11+, an OpenAI API key, and ngrok (if you need external access)

```bash
# 1. Clone and create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
# Optionally set BASE_URL to your ngrok URL for external interview links
```

**.env**
```
OPENAI_API_KEY=sk-...
BASE_URL=http://localhost:3000   # or https://your-ngrok-url.ngrok-free.app
PORT=3000
```

```bash
# 4. Start the server
python main.py
```

Dashboard is available at http://localhost:3000.

### External Access with ngrok

Interview links need to be accessible from the interviewee's device. To expose your local server:

```bash
ngrok http 3000
```

Copy the `https://` URL ngrok gives you, set it as `BASE_URL` in `.env`, and restart the server. All newly created interview links will use that URL.

---

## Usage

1. **Open the dashboard** at http://localhost:3000
2. **Fill in Setup** — describe your ICP and list your hypotheses (one per line), then click Save
3. **Create an interview** — click `+ New`, give it a name, click Create
4. **Share the link** — click Copy Link and send it to your interviewee
5. **Interviewee joins** — they open the link in any browser, grant mic access, and the AI takes over
6. **Review results** — once the interview completes, click View Report to read the markdown report
7. **Ask questions** — type anything in the Insights panel to query across all completed interviews

---

## API Reference

| Method | Route | Description |
|---|---|---|
| GET | `/api/config` | Get saved ICP and hypotheses |
| POST | `/api/config` | Save ICP and hypotheses |
| POST | `/api/interviews` | Create a new interview |
| GET | `/api/interviews` | List all interviews |
| GET | `/api/interviews/:id` | Get interview details, extracted insights, and report |
| POST | `/api/interviews/:id/session-token` | Generate ephemeral OpenAI Realtime token |
| POST | `/api/interviews/:id/complete` | Submit transcript and trigger post-processing |
| POST | `/api/insights` | Ask a question across all completed interviews |

Auto-generated interactive docs available at http://localhost:3000/docs.
