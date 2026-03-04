# Project Summary — Insight Loop MVP

## Artifacts Created

```
context/
├── rough-idea.md                        # Original concept
├── idea-honing.md                       # Requirements Q&A (8 questions)
├── summary.md                           # This file
├── research/                            # (no external research conducted — domain clear)
├── design/
│   └── detailed-design.md              # Full system design
└── implementation/
    └── plan.md                          # 5-step implementation plan with checklist
```

---

## What We're Building

A local web app that closes the loop between a founder's market research hypotheses and structured customer insights — in one hour.

**Core loop:** AI conducts voice interview → browser submits transcript → backend extracts structured insights + generates report → founder queries insights via chat.

---

## Design Summary

| Area | Decision |
|------|----------|
| Interview medium | Interviewee joins via browser URL |
| Voice AI | OpenAI Realtime API (`gpt-4o-realtime-preview`) via WebRTC |
| Session auth | Server issues ephemeral token; browser connects directly to OpenAI |
| Post-processing | GPT-4o generates `extracted.json` + `report.md` from transcript |
| Insights Q&A | GPT-4o queries `extracted.json` only (not full transcripts) |
| Storage | Flat files: JSON + markdown |
| External access | `BASE_URL` env var (set to ngrok URL when sharing links externally) |
| Frontend | Vanilla HTML/CSS/JS, no build step |
| Backend | Python + FastAPI + Uvicorn |

**Two output files per interview:**
- `extracted.json` — structured: pain points, workflows, tools, hypothesis assessments
- `report.md` — human-readable narrative summary

---

## Implementation Plan (5 Steps)

- [ ] **Step 1** — Project scaffold, config API (`GET/POST /api/config`), flat-file helpers
- [ ] **Step 2** — Interview CRUD API + founder dashboard (3-panel UI: Setup, Interviews, Insights shell)
- [ ] **Step 3** — Interview page + Realtime session token + live WebRTC AI interview
- [ ] **Step 4** — `/complete` endpoint: save transcript → `extracted.json` → `report.md` → mark completed
- [ ] **Step 5** — Insights Q&A panel: query across all `extracted.json` files

---

## Next Steps

1. Create a `.env` file from `.env.example` and add your `OPENAI_API_KEY`
2. Run `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Start ngrok (`ngrok http 3000`) and set `BASE_URL` in `.env` before sharing interview links
4. Follow the implementation checklist in `context/implementation/plan.md` step by step
5. After each step, verify the demo described in the plan before moving on

## Areas to Watch

- **WebRTC + ngrok**: The interview page must be served over HTTPS for `getUserMedia` to work in most browsers. ngrok provides HTTPS by default — make sure `BASE_URL` uses the `https://` ngrok URL.
- **Transcript event format**: The Realtime API emits several event types. Only `conversation.item.completed` events with `type: "message"` should be captured for the transcript array.
- **Post-processing latency**: Two sequential GPT-4o calls after interview completion may take 15-30 seconds. The dashboard status will show `in_progress` until both complete — this is expected.
- **Insights context size**: Keep extracted.json files concise. If many interviews accumulate, the insights prompt may grow large — consider truncating `evidence_quotes` to 2-3 per hypothesis.
