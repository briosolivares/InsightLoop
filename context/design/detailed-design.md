# Detailed Design — Insight Loop MVP

## Overview

Insight Loop is a local web application that enables founders to conduct AI-powered primary market research interviews. A founder defines their ICP and hypotheses, the AI voice agent autonomously interviews participants via browser, transcripts are processed into structured insights and reports, and the founder can query insights across all interviews through a chat interface.

**Core loop:** Interview (AI voice) → Transcript → Extracted Insights + Report → Insights Q&A

---

## Detailed Requirements

### Functional Requirements

1. **Project Setup**
   - Founder can input and save an ICP (text description)
   - Founder can input and save a list of hypotheses to test

2. **Interview Management**
   - Founder can create an interview with a name (required) and notes (optional)
   - System generates a unique session ID and shareable URL
   - Founder can copy the interview link from the dashboard
   - Interviewee opens the URL in a browser, grants mic permission, and the AI conducts the interview
   - Dashboard shows interview status: `pending` | `in_progress` | `completed`

3. **AI Voice Interview**
   - Uses OpenAI Realtime API (`gpt-4o-realtime-preview`) via WebRTC
   - AI is briefed with the founder's ICP and hypotheses
   - AI generates opening questions from the hypotheses
   - AI asks dynamic follow-up questions during the conversation
   - AI wraps up and ends the interview after covering all hypotheses

4. **Transcription**
   - Browser accumulates all transcript events locally during the interview
   - On interview end, browser sends the full transcript in a single `POST /api/interviews/:id/complete` call

5. **Post-Interview Processing** (triggered by `/complete`)
   - Backend saves `transcript.json`
   - Calls GPT-4o to generate `extracted.json` (structured machine-readable insights)
   - Calls GPT-4o to generate `report.md` (human-readable summary, informed by extracted insights)
   - Marks interview status as `completed`

6. **Insights Q&A**
   - Founder types a natural language question in the Insights panel
   - Backend loads `extracted.json` from each completed interview (not full transcripts)
   - Queries GPT-4o with the structured extractions + question
   - Response displayed in chat interface

### Non-Functional Requirements

- Runs locally on the founder's machine
- Interview links use a configurable `BASE_URL` env var (default: `http://localhost:3000`); set to ngrok URL for external access
- No database — flat files only (JSON + markdown)
- `.env` configuration: `OPENAI_API_KEY`, `BASE_URL` (default `http://localhost:3000`), `PORT` (default `3000`)
- No authentication needed (local use only)
- Simple, functional UI — no design system required
- No live transcript rendering on the interview page

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                 Founder's Machine                │
│                                                  │
│   ┌─────────────────┐   ┌─────────────────────┐ │
│   │ Founder Dashboard│   │   Python Backend    │ │
│   │   (browser)      │◄─►│   FastAPI + pathlib │ │
│   └─────────────────┘   └──────────┬──────────┘ │
│                                    │             │
│                          GPT-4o Chat Completions │
│                          (post-processing + Q&A) │
└────────────────────────────────────┼────────────┘
                                     │ OpenAI API

Interviewee (any device, any network):
┌──────────────────────────────────────────────────────┐
│  Browser → BASE_URL/interview/:id                    │
│  Mic permission granted                              │
│  POST /api/interviews/:id/session-token → get token  │
│  WebRTC direct to OpenAI Realtime API ─────────────► OpenAI
│  Accumulate transcript locally                       │ (gpt-4o-realtime)
│  On end → POST /api/interviews/:id/complete          │
└──────────────────────────────────────────────────────┘
```

### Key Architectural Decision: Client-Direct WebRTC

The interviewee's browser connects **directly to OpenAI's Realtime API** via WebRTC using a short-lived ephemeral session token. The backend:
- Generates the ephemeral token (one API call, configured with ICP + hypotheses)
- Receives the full transcript in a single call when the interview ends
- Runs all post-processing (extract → report → save → mark complete)

This avoids the complexity of server-side audio proxying and streaming transcript state.

### Fallback Architecture

If WebRTC Realtime audio fails, the system can fall back to a chained pipeline:

```
Browser mic → STT (Whisper) → GPT-4o (generate response) → TTS (gpt-4o-mini-tts) → Browser speaker
```

The fallback is **not implemented in MVP** but the architecture accommodates it:
- The session token endpoint is the only Realtime-specific integration point
- Post-processing and insights are already decoupled from the transport layer
- Swapping the interview page's WebRTC logic for a chained loop requires no backend changes

---

## Components and Interfaces

### 1. Backend — `main.py` (Python / FastAPI)

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Serve founder dashboard HTML |
| `/interview/:id` | GET | Serve interviewee interview page HTML |
| `/api/config` | GET | Read ICP + hypotheses from disk |
| `/api/config` | POST | Save ICP + hypotheses to disk |
| `/api/interviews` | GET | List all interviews (meta only) |
| `/api/interviews` | POST | Create new interview, return `{id, url}` |
| `/api/interviews/:id` | GET | Get interview details (meta + extracted + report if done) |
| `/api/interviews/:id/session-token` | POST | Generate OpenAI ephemeral session token with ICP + hypotheses injected |
| `/api/interviews/:id/complete` | POST | Receive full transcript, run post-processing, mark completed |
| `/api/insights` | POST | Q&A — `{question}` → `{answer}` using extracted.json from all interviews |

> **Removed:** `POST /api/interviews/:id/transcript` — transcript is no longer streamed incrementally.

### 2. Founder Dashboard — `public/dashboard.html`

Three-panel layout:

```
┌──────────────────────────────────────────────────────────┐
│  Insight Loop                                            │
├──────────────┬──────────────────────┬────────────────────┤
│  SETUP       │  INTERVIEWS          │  INSIGHTS          │
│              │                      │                    │
│  ICP:        │  [+ New Interview]   │  Ask a question:   │
│  [textarea]  │                      │  [input + send]    │
│              │  ● Interview A  ✓    │                    │
│  Hypotheses: │  ● Interview B  ●    │  > What's the #1   │
│  [textarea]  │  ● Interview C  ○    │    pain point?     │
│              │                      │                    │
│  [Save]      │  [Copy Link] [View]  │  < Most users      │
│              │                      │    mentioned...    │
└──────────────┴──────────────────────┴────────────────────┘

Legend: ✓ completed  ● in_progress  ○ pending
```

### 3. Interview Page — `public/interview.html`

Minimal interviewee-facing page. No live transcript display.

```
┌──────────────────────────────────────┐
│                                      │
│        AI Market Research            │
│            Interview                 │
│                                      │
│        [ state message here ]        │
│                                      │
└──────────────────────────────────────┘
```

| State | Message shown |
|-------|--------------|
| `waiting-for-mic` | "Click to allow microphone access" |
| `connecting` | "Connecting to your interviewer..." |
| `in_progress` | "Interview in progress" |
| `completed` | "Interview complete. Thank you!" |

### 4. AI Interview Agent (OpenAI Realtime API)

Configured via ephemeral session token with:
- **Model**: `gpt-4o-realtime-preview`
- **Modalities**: `["audio", "text"]`
- **Turn detection**: Server VAD (automatic)
- **System prompt**: Interview instructions + ICP + hypotheses

**System Prompt Template:**
```
You are a professional market research interviewer conducting a research
interview on behalf of a founder.

Ideal Customer Profile:
{icp}

Hypotheses to validate:
{hypotheses_numbered_list}

Instructions:
- Introduce yourself warmly as an AI research assistant
- Ask open-ended questions to probe each hypothesis
- Ask natural follow-up questions based on what the interviewee says
- Be conversational, curious, and empathetic — not robotic
- Cover all hypotheses before ending
- After covering all hypotheses, thank the interviewee and close the session
- Keep the interview to approximately 15-20 minutes
```

---

## Data Models

### Directory Structure

```
data/
├── config.json                    # ICP + hypotheses
└── interviews/
    └── {interview-id}/
        ├── meta.json              # Interview metadata + status
        ├── transcript.json        # Raw transcript (sent from browser on complete)
        ├── extracted.json         # Structured machine-readable insights
        └── report.md              # Human-readable summary report
```

### `config.json`

```json
{
  "icp": "Early-stage SaaS founders, 1-10 employees, B2B focus...",
  "hypotheses": [
    "Founders struggle to find qualified interview candidates",
    "Current research tools are too complex for non-technical founders",
    "Founders want structured output, not just raw recordings"
  ],
  "updated_at": "2026-03-03T10:00:00Z"
}
```

### `interviews/{id}/meta.json`

```json
{
  "id": "a1b2c3d4",
  "name": "Interview with Sarah Chen",
  "notes": "Referred by YC community. B2B SaaS founder.",
  "status": "pending",
  "created_at": "2026-03-03T10:00:00Z",
  "completed_at": null,
  "url": "https://abc123.ngrok.io/interview/a1b2c3d4"
}
```

### Interview Status Transitions

```
[created]     [session established]    [/complete processed]
  pending  ──────────────────────►  in_progress  ──────────────►  completed
```

- `pending` — interview created, link not yet opened
- `in_progress` — interviewee's browser successfully establishes the Realtime session (backend updated via `POST /api/interviews/:id/session-token` response)
- `completed` — `/complete` endpoint finishes saving transcript, extracted.json, and report.md

### `interviews/{id}/transcript.json`

```json
[
  {
    "role": "assistant",
    "content": "Hi! Thanks for joining this research interview...",
    "timestamp": "2026-03-03T10:05:00Z"
  },
  {
    "role": "user",
    "content": "Happy to be here.",
    "timestamp": "2026-03-03T10:05:08Z"
  }
]
```

### `interviews/{id}/extracted.json`

```json
{
  "top_pain_points": [
    "Difficulty finding qualified interviewees",
    "No structured way to capture insights from calls"
  ],
  "current_workflows": [
    "Manual outreach via LinkedIn",
    "Recording Zoom calls and reviewing them manually"
  ],
  "tools_mentioned": [
    "Notion", "Zoom", "Calendly"
  ],
  "hypothesis_assessment": [
    {
      "hypothesis": "Founders struggle to find qualified interview candidates",
      "status": "confirmed",
      "evidence_quotes": [
        "It takes me like two weeks just to get five people on a call"
      ]
    },
    {
      "hypothesis": "Current research tools are too complex for non-technical founders",
      "status": "inconclusive",
      "evidence_quotes": []
    }
  ]
}
```

Status values: `"confirmed"` | `"refuted"` | `"inconclusive"`

### `interviews/{id}/report.md`

Human-readable markdown generated from transcript + extracted.json:

- **Summary** — 2-3 sentence overview of the interview
- **Key Pain Points** — drawn from `extracted.top_pain_points`
- **Current Workflows** — drawn from `extracted.current_workflows`
- **Tools Mentioned** — drawn from `extracted.tools_mentioned`
- **Hypothesis Validation** — per hypothesis from `extracted.hypothesis_assessment`
- **Notable Quotes** — pulled from `evidence_quotes`

---

## Key Flows

### Interview Session Flow

```
Founder                Backend              Interviewee Browser       OpenAI
  │                       │                        │                    │
  │ POST /api/interviews   │                        │                    │
  │──────────────────────►│                        │                    │
  │ {id, url}             │                        │                    │
  │◄──────────────────────│  status: pending        │                    │
  │                       │                        │                    │
  │ (shares URL manually) │                        │                    │
  │                       │  GET /interview/:id    │                    │
  │                       │◄───────────────────────│                    │
  │                       │───────────────────────►│ (page loads)       │
  │                       │                        │ (request mic)      │
  │                       │  POST /session-token   │                    │
  │                       │◄───────────────────────│                    │
  │                       │  (status → in_progress)│                    │
  │                       │──────────────────────────────────────────► │
  │                       │       {ephemeral_token}                    │
  │                       │◄──────────────────────────────────────────│
  │                       │───────────────────────►│                    │
  │                       │                        │ WebRTC connect     │
  │                       │                        │───────────────────►│
  │                       │                        │ ◄── AI speaks/listens
  │                       │                        │ (accumulate turns) │
  │                       │                        │ (AI signals end)   │
  │                       │  POST /complete        │                    │
  │                       │  {transcript: [...]}   │                    │
  │                       │◄───────────────────────│                    │
  │                       │  save transcript.json  │                    │
  │                       │──────────────────────────────────────────► │
  │                       │  GPT-4o → extracted.json + report.md       │
  │                       │◄──────────────────────────────────────────│
  │                       │  status → completed    │                    │
  │ (dashboard refreshes) │                        │                    │
```

### Insights Q&A Flow

```
Founder asks: "What's the #1 pain point?"
     │
     ▼
Backend loads extracted.json from all completed interviews
     │
     ▼
Constructs GPT-4o prompt:
  "Here are structured research extractions from N interviews:
   [extracted.json contents — pain points, workflows, hypothesis assessments]

   Question: What's the #1 pain point?
   Answer concisely based on the data:"
     │
     ▼
Returns answer to dashboard chat UI
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Interviewee denies mic permission | Show: "Microphone access is required to join this interview." |
| OpenAI API key missing/invalid | Backend returns 500; dashboard shows config error banner |
| Session token request fails | Interview page shows retry button, status stays `pending` |
| Network drops mid-interview | Browser sends whatever transcript was accumulated to `/complete`; partial flag set in meta.json |
| Post-processing fails | Status marked `completed`, report.md contains error message; raw transcript still saved |
| Insights Q&A with no completed interviews | Returns "No completed interviews yet." |
| `/complete` called on already-completed interview | Return 409; no reprocessing |

---

## Testing Strategy

For the MVP, tests are lightweight — manual curl + browser verification at each step:

- **API routes**: curl tests for config CRUD, interview create/list/get
- **File storage**: Verify correct JSON structure written after each write operation
- **Session token**: Verify ephemeral token returned and accepted by browser WebRTC
- **Transcript submission**: POST sample transcript to `/complete`, verify all 3 output files created
- **Post-processing**: Inspect `extracted.json` structure matches schema; verify `report.md` has all sections
- **Insights Q&A**: Query with 1-2 sample extracted.json files loaded, verify coherent answer

---

## Appendices

### A. Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | Python + FastAPI + Uvicorn | Clean async support, Pydantic validation, auto docs at `/docs` |
| Frontend | Vanilla HTML/CSS/JS | No build step — fastest for MVP |
| Voice API | OpenAI Realtime API (`gpt-4o-realtime-preview`) | Speech-to-speech, low latency, browser WebRTC native |
| Transport | WebRTC (client-direct) | No server audio proxy; ephemeral token keeps API key server-side |
| Post-processing | OpenAI Chat Completions (`gpt-4o`) | Structured JSON extraction + markdown generation |
| Insights context | `extracted.json` only | Keeps prompts small and responses reliable vs. full transcripts |
| Storage | JSON + Markdown flat files | Zero deps, human-readable, sufficient for MVP scale |
| Session IDs | `uuid.uuid4()` | Built-in Python stdlib, no extra deps |
| External access | `BASE_URL` env var + ngrok | Simple, no code changes needed to switch local ↔ public |
| Dependency mgmt | `requirements.txt` + `.venv` | Standard Python virtualenv isolation |

### B. Alternative Approaches Considered

- **Node.js + Express**: Originally considered; switched to FastAPI for cleaner async support, Pydantic request validation, and auto-generated API docs at `/docs`.
- **Streaming transcript to backend during interview**: Adds real-time complexity; single `/complete` call is simpler and sufficient.
- **Full transcript context for insights Q&A**: Creates large prompts, slow responses; `extracted.json` captures the signal without the noise.
- **Server-side WebSocket relay**: More audio control, but adds latency and eliminates the need for client-direct WebRTC.
- **SQLite**: Better querying for insights, but flat files are sufficient for MVP scale.

### C. Out of Scope for MVP

- ICP qualification / outreach (Phase 2)
- Authentication / multi-user support
- Export (PDF, CSV)
- Interview scheduling
- Live transcript display during interview
- Interview duration limits / auto-termination timer
- Chained STT → LLM → TTS fallback (architecture supports it; not implemented)
