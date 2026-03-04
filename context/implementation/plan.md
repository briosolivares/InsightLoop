# Implementation Plan — Insight Loop MVP

## Checklist

- [x] Step 1: Project scaffold, config API, and data layer
- [ ] Step 2: Interview CRUD API and founder dashboard shell
- [ ] Step 3: Interview page, Realtime session token, and live AI interview
- [ ] Step 4: Interview completion, post-processing, and structured output
- [ ] Step 5: Insights Q&A panel

---

## Step 1: Project Scaffold, Config API, and Data Layer ✓ COMPLETED

### Objective
Bootstrap the Python FastAPI project, establish the flat-file data layer, and implement the config API so the founder can save and retrieve their ICP and hypotheses.

### What Was Built

**Project structure created:**
```
insight-loop/
├── main.py
├── requirements.txt
├── .env.example
├── .env
├── .gitignore
├── .venv/
├── public/
│   ├── dashboard.html      (placeholder)
│   └── interview.html      (placeholder)
└── data/
    └── interviews/         (empty dir, git-ignored contents)
```

**`requirements.txt` dependencies installed into `.venv`:**
- `fastapi` — web framework
- `uvicorn[standard]` — ASGI server with hot reload
- `python-dotenv` — env var loading
- `openai` — OpenAI SDK
- `python-multipart` — required by FastAPI for form handling

**`.env.example`:**
```
OPENAI_API_KEY=sk-...
BASE_URL=http://localhost:3000
PORT=3000
```

**`main.py` — implemented:**
- Loads `.env` with `python-dotenv`
- Serves `public/` as static files via `StaticFiles`
- `GET /api/config` — reads `data/config.json`, returns `{}` if not found
- `POST /api/config` — writes `{ icp, hypotheses, updated_at }` to `data/config.json`
- Request body validated with Pydantic `ConfigPayload` model
- All file reads/writes use `pathlib.Path` with try/except
- Routes `GET /` → `dashboard.html`, `GET /interview/{id}` → `interview.html`

**Data layer helpers (in main.py):**
- `read_json(filepath)` — reads and parses a dict JSON file, returns None if missing
- `read_json_list(filepath)` — same but for list-typed files (transcripts)
- `write_json(filepath, data)` — ensures parent directory exists, writes JSON with 2-space indent

**Run with:**
```bash
source .venv/bin/activate
python main.py
# API docs available at http://localhost:3000/docs
```

### Test Results ✓
- `POST /api/config` → 200, `data/config.json` written correctly
- `GET /api/config` → returns saved config
- `GET /api/config` (before any save) → returns `{}`
- `GET /` → serves `public/dashboard.html`

### Integration
Foundation for all subsequent steps. Config saved here is loaded into the AI system prompt in Step 3.

### Demo ✓ Verified
Server starts with `.venv/bin/python main.py`. ICP and hypotheses saved via curl persist to `data/config.json` and survive restarts. API docs available at `http://localhost:3000/docs`.

---

## Step 2: Interview CRUD API and Founder Dashboard Shell

### Objective
Implement the interview management API (create, list, get) and build the functional founder dashboard — a three-panel web UI where the founder can save their setup, create interviews, and copy shareable links.

### Implementation Guidance

**New API routes in `server.js`:**
- `POST /api/interviews` — body: `{ name, notes? }`
  - Generate `id = randomUUID()`
  - Build `url = process.env.BASE_URL + '/interview/' + id`
  - Write `data/interviews/{id}/meta.json` with `{ id, name, notes, status: 'pending', created_at, completed_at: null, url }`
  - Return `{ id, url }`
- `GET /api/interviews` — read all `data/interviews/*/meta.json`, return array sorted by `created_at` descending
- `GET /api/interviews/:id` — return `meta.json` for that interview; if completed, also return contents of `report.md` and `extracted.json`

**`public/dashboard.html` — three-panel layout:**

*Setup panel (left):*
- Textarea for ICP
- Textarea for hypotheses (one per line)
- Save button → `POST /api/config`
- On page load, `GET /api/config` and populate fields

*Interviews panel (center):*
- "New Interview" button → opens a small inline form: interview name input + optional notes input + Create button
- Create button → `POST /api/interviews`, adds new row to list
- Interview list renders each `meta.json` as a row:
  - Name
  - Status badge: `○ pending` | `● in progress` | `✓ completed`
  - "Copy Link" button → copies `meta.url` to clipboard
  - "View" button (only if completed) → opens a modal/panel showing `report.md` rendered as text
- Polls `GET /api/interviews` every 5 seconds to refresh statuses

*Insights panel (right):*
- Placeholder: "Insights will appear here once interviews are completed."
- Chat input disabled for now

**CSS:** Minimal inline styles. Three equal-width columns. No external dependencies.

### Test Requirements
- `POST /api/interviews` with `{ name: "Test Interview" }` → 201, `data/interviews/{id}/meta.json` created with `status: "pending"`, `url` contains `BASE_URL`
- `GET /api/interviews` → returns array including the new interview
- `GET /api/interviews/:id` → returns meta for that id
- Open `http://localhost:3000` in browser → dashboard renders with 3 panels
- Save ICP + hypotheses via Setup panel → `data/config.json` updated
- Create interview via dashboard → new row appears in Interviews panel with Copy Link button

### Integration
Builds on Step 1's config API and file helpers. The interview URLs generated here are used by the interview page in Step 3.

### Demo
Founder opens `http://localhost:3000`, fills in ICP and hypotheses, saves them, creates a new interview, and copies the shareable link. Dashboard shows the interview as `pending`. All data persists on server restart.

---

## Step 3: Interview Page, Realtime Session Token, and Live AI Interview

### Objective
Implement the interviewee-facing interview page and the session token endpoint. The browser requests an ephemeral token from the backend, connects directly to OpenAI's Realtime API via WebRTC, and the AI conducts the interview autonomously using the founder's hypotheses. The browser accumulates the full transcript locally.

### Implementation Guidance

**New API route:**
- `POST /api/interviews/:id/session-token`
  - Read `data/config.json` to get ICP + hypotheses
  - Build the AI system prompt from the template (see design doc)
  - Call OpenAI API to create an ephemeral Realtime session:
    ```js
    const session = await openai.beta.realtime.sessions.create({
      model: 'gpt-4o-realtime-preview',
      modalities: ['audio', 'text'],
      instructions: systemPrompt,
      voice: 'alloy',
      turn_detection: { type: 'server_vad' }
    });
    ```
  - Update `meta.json` status to `in_progress`
  - Return `{ client_secret: session.client_secret.value }`

**`public/interview.html` — four states only, no transcript display:**

*State machine:*
```
waiting-for-mic → connecting → in_progress → completed
```

*On page load:*
- Extract interview `id` from URL path
- Show `waiting-for-mic` state with a "Start Interview" button

*On button click:*
- `getUserMedia({ audio: true })` → on success, transition to `connecting`
- `POST /api/interviews/:id/session-token` → get `client_secret`
- Connect to OpenAI Realtime API via WebRTC:
  ```js
  const pc = new RTCPeerConnection();
  // Add local audio track
  pc.addTrack(localStream.getTracks()[0]);
  // Play remote audio (AI voice)
  pc.ontrack = e => { audioEl.srcObject = e.streams[0]; };
  // Create data channel for events
  const dc = pc.createDataChannel('oai-events');
  // SDP offer/answer with OpenAI
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const sdpResponse = await fetch(
    `https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview`,
    { method: 'POST', headers: { Authorization: `Bearer ${client_secret}`, 'Content-Type': 'application/sdp' }, body: offer.sdp }
  );
  await pc.setRemoteDescription({ type: 'answer', sdp: await sdpResponse.text() });
  ```
- Transition to `in_progress`

*Transcript accumulation:*
- Listen to `dc` data channel messages
- On `conversation.item.completed` events, push `{ role, content, timestamp }` to local `transcript` array
- On `session.done` or when the AI signals the conversation is over (detect via a final assistant turn ending with a farewell phrase or `response.done` with no more turns), transition to `completed` and call Step 4's `/complete` endpoint

### Test Requirements
- `POST /api/interviews/:id/session-token` → returns `{ client_secret: "..." }` and `meta.json` updated to `in_progress`
- Dashboard shows interview status updated to `● in progress` (via polling)
- Open interview URL in browser → page loads, shows "Start Interview" button
- Click button → browser requests mic, AI voice begins speaking the interview introduction
- Speaking back to the AI → AI responds with follow-up questions
- Dashboard polling picks up `in_progress` status change

### Integration
Consumes config from Step 1, interview meta from Step 2. The transcript accumulated here is submitted to Step 4's `/complete` endpoint.

### Demo
Founder creates an interview, copies the link, opens it in a second browser tab, grants mic, and the AI conducts a live voice interview based on the configured hypotheses. Dashboard shows the interview as `in progress`.

---

## Step 4: Interview Completion, Post-Processing, and Structured Output

### Objective
When the interview ends, the browser submits the full accumulated transcript to the backend. The backend saves the transcript, runs two GPT-4o calls to generate `extracted.json` and `report.md`, marks the interview as completed, and the dashboard reflects the new state with a viewable report.

### Implementation Guidance

**New API route:**
- `POST /api/interviews/:id/complete`
  - Body: `{ transcript: [...] }`
  - If interview already `completed`, return 409
  - Save `data/interviews/{id}/transcript.json`
  - Call GPT-4o for structured extraction:
    ```
    System: You are a qualitative research analyst.
    User: Here is a transcript from a market research interview:
    {transcript as formatted text}

    Extract the following and respond with valid JSON only:
    {
      "top_pain_points": [],
      "current_workflows": [],
      "tools_mentioned": [],
      "hypothesis_assessment": [
        { "hypothesis": "...", "status": "confirmed|refuted|inconclusive", "evidence_quotes": [] }
      ]
    }

    Hypotheses to assess: {hypotheses list}
    ```
  - Save response as `data/interviews/{id}/extracted.json`
  - Call GPT-4o for report generation:
    ```
    System: You are a market research analyst writing a report for a founder.
    User: Based on this interview transcript and structured extraction, write a
    markdown report with these sections:
    # Interview Report: {interview name}
    ## Summary
    ## Key Pain Points
    ## Current Workflows
    ## Tools Mentioned
    ## Hypothesis Validation
    ## Notable Quotes

    Transcript: {transcript}
    Extracted insights: {extracted.json}
    ```
  - Save as `data/interviews/{id}/report.md`
  - Update `meta.json`: `status = 'completed'`, `completed_at = now`
  - Return `{ success: true }`

**Update `GET /api/interviews/:id`** to include report and extracted contents when status is `completed`.

**Update dashboard** — "View" button on completed interviews opens a panel showing the `report.md` content rendered as preformatted text.

**Update interview page** — after successfully POSTing to `/complete`, transition page to `completed` state ("Interview complete. Thank you!").

### Test Requirements
- `POST /api/interviews/:id/complete` with a sample transcript array → 200
- Verify `data/interviews/{id}/transcript.json` written correctly
- Verify `data/interviews/{id}/extracted.json` matches the schema (all 4 keys present, `hypothesis_assessment` has one entry per hypothesis)
- Verify `data/interviews/{id}/report.md` contains all 6 sections
- Verify `meta.json` updated to `status: "completed"` with `completed_at` set
- Dashboard polling picks up completed status; "View" button appears
- Click "View" → report content displayed
- Calling `/complete` again on same id → 409

### Integration
Consumes transcript from Step 3's interview page. `extracted.json` generated here powers Step 5's Insights Q&A.

### Demo
Full end-to-end flow works: conduct an interview → interview ends → dashboard flips to `completed` within polling interval → founder clicks "View" → sees the full structured report with hypothesis validation, pain points, and notable quotes.

---

## Step 5: Insights Q&A Panel

### Objective
Wire up the Insights panel so the founder can ask natural language questions across all completed interviews. The backend loads only `extracted.json` from each interview, queries GPT-4o, and streams the answer back to the chat UI.

### Implementation Guidance

**New API route:**
- `POST /api/insights`
  - Body: `{ question: "..." }`
  - Read all `data/interviews/*/extracted.json` files (only from completed interviews)
  - If none found, return `{ answer: "No completed interviews yet." }`
  - Build GPT-4o prompt:
    ```
    System: You are a market research analyst helping a founder interpret
    customer interview data. Answer questions concisely based only on the
    provided interview extractions.

    User: Here are structured extractions from {N} completed interviews:

    Interview 1 — "{interview name}":
    {extracted.json as formatted JSON}

    Interview 2 — "{interview name}":
    {extracted.json as formatted JSON}

    ...

    Question: {question}
    ```
  - Return `{ answer: "..." }`

**Update `public/dashboard.html` — Insights panel:**
- Enable chat input
- On submit → `POST /api/insights` with `{ question }`
- Append user question and AI answer to chat history in the panel
- Show loading indicator while waiting for response
- Handle error state gracefully ("Could not get answer — try again")

### Test Requirements
- `POST /api/insights` with no completed interviews → returns "No completed interviews yet."
- `POST /api/insights` with 1 completed interview and a sample extracted.json on disk → returns a coherent, relevant answer
- Multiple completed interviews → answer synthesizes across all of them
- In dashboard: type a question, hit send, answer appears in chat
- Error case: if API call fails, error message shown in chat (not a broken UI)

### Integration
Depends on `extracted.json` files created in Step 4. Completes the core loop: interview → transcript → extracted → insights Q&A.

### Demo
Founder has completed 1+ interviews. They open the Insights panel, type "What is the #1 pain point mentioned across my interviews?", and receive a synthesized answer drawn from the structured extractions. The full core loop — from AI interview to actionable insight — is operational.
