# Idea Honing — Insight Loop

Requirements clarification Q&A for the Insight Loop project.

---

## Q1: MVP Scope

**Q:** Given the end-to-end pipeline (ICP → qualify → outreach → interview → transcribe → insights → report), which part is the core MVP for this hour? Are we building the full pipeline end-to-end (thin slice), or focusing on one specific stage?

**A:** Focus on the core value loop: **interview → transcribe → insights → report**. The founder should then be able to ask the agent natural language questions across all interviews (e.g., "What's the number one pain point the people I've interviewed have?").

---

## Q2: Role of the Voice Agent

**Q:** When you say "voice agent" for the interview — what role does the AI play? (A) AI conducts the interview autonomously, (B) AI assists the founder in real-time during the call, or (C) AI processes pre-recorded/uploaded audio after the fact?

**A:** The AI conducts the interview autonomously. The founder provides a set of **hypotheses** they want to test. The AI generates a question list from those hypotheses and, during the live interview, dynamically asks follow-up questions to probe deeper and validate/invalidate each hypothesis.

---

## Q3: Interview Medium

**Q:** How does the interviewee actually join the interview? (A) Phone call — AI calls their number, (B) Web/browser link — interviewee joins via URL, (C) In-person — speaking into the founder's mic, (D) Something else?

**A:** The interviewee joins via a **URL in their browser** — a web-based audio session.

---

## Q4: Founder's Interface

**Q:** What does the founder's interface look like for setting up interviews and querying insights afterward?

**A:** A **local web app (ops dashboard)** with:
1. **Setup panel** — input hypotheses and ICP
2. **Interviews panel** — create interviews, see active sessions, view past interviews
3. **Insights panel** — ask meta questions across all interviews (e.g., "What's the #1 pain point?")

Simple UI, no heavy design needed.

---

## Q5: AI & Tech Stack

**Q:** When you say "local AI," do you mean models running fully on-device (e.g., Ollama/LLaMA), or are API calls to Claude/OpenAI acceptable? And do you have preferences for the web framework (e.g., React, plain HTML, Next.js) or backend language?

**A:** Use **OpenAI's API**, specifically the **Realtime speech-to-speech API** for the interview voice agent. No strong framework preference stated.

---

## Q6: Data Persistence

**Q:** For the MVP, how should interview data be stored? (A) Simple flat files (JSON/markdown on disk), (B) Local database (SQLite), (C) Doesn't matter, simplest thing that works?

**A:** **Flat files (JSON/markdown on disk)** — simplest thing that works.

---

## Q7: Insights & Report Format

**Q:** When the AI extracts insights after an interview, what should the output look like? And for the insights panel Q&A, is it a simple chat box where the founder types questions?

**A:** Post-interview output: **raw transcript + summary report**. Insights panel: **simple chat box** where the founder types questions and gets answers drawn from all interviews.

---

## Q8: Interview Creation Flow

**Q:** When the founder creates an interview in the dashboard, what's the flow? Do they enter the interviewee's name, the system generates a shareable link, and the founder sends it manually? Or is there more to it?

**A:**
1. Founder creates interview in dashboard (name required, notes optional)
2. System generates a unique interview session + shareable link
3. Founder copies and sends the link manually
4. Interviewee opens the link, browser requests mic permission
5. AI conducts the interview via OpenAI Realtime API
6. System processes the recording (transcription + insight extraction + summary report)
7. Dashboard shows interview status: **Pending → In Progress → Completed**, with results visible on completion
