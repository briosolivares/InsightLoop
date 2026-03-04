import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from storage import (CONFIG_FILE, INTERVIEWS_DIR, init_storage, read_json,
                     write_json)
from agent import (create_realtime_session, format_transcript, run_extraction,
                   run_insights, run_report)

load_dotenv()

app = FastAPI()
init_storage()


# --- Pydantic models ---

class ConfigPayload(BaseModel):
    icp: str | None = None
    hypotheses: list[str] | None = None


class InterviewPayload(BaseModel):
    name: str
    notes: str | None = None


class CompletePayload(BaseModel):
    transcript: list


class InsightsPayload(BaseModel):
    question: str


# --- Config routes ---

@app.get("/api/config")
def get_config():
    return read_json(CONFIG_FILE) or {}


@app.post("/api/config")
def save_config(payload: ConfigPayload):
    if payload.icp is None and payload.hypotheses is None:
        raise HTTPException(status_code=400, detail="icp or hypotheses required")
    existing = read_json(CONFIG_FILE) or {}
    config = {
        "icp": payload.icp if payload.icp is not None else existing.get("icp", ""),
        "hypotheses": payload.hypotheses if payload.hypotheses is not None else existing.get("hypotheses", []),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(CONFIG_FILE, config)
    return config


# --- Interview routes ---

@app.post("/api/interviews", status_code=201)
def create_interview(payload: InterviewPayload):
    interview_id = str(uuid4())
    url = f"{os.getenv('BASE_URL', 'http://localhost:3000')}/interview/{interview_id}"
    meta = {
        "id": interview_id,
        "name": payload.name,
        "notes": payload.notes or "",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "url": url,
    }
    write_json(INTERVIEWS_DIR / interview_id / "meta.json", meta)
    return {"id": interview_id, "url": url}


@app.get("/api/interviews")
def list_interviews():
    interviews = []
    for meta_file in INTERVIEWS_DIR.glob("*/meta.json"):
        meta = read_json(meta_file)
        if meta:
            interviews.append(meta)
    interviews.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return interviews


@app.get("/api/interviews/{interview_id}")
def get_interview(interview_id: str):
    interview_dir = INTERVIEWS_DIR / interview_id
    meta = read_json(interview_dir / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="Interview not found")
    result = dict(meta)
    if meta.get("status") == "completed":
        extracted = read_json(interview_dir / "extracted.json")
        report_path = interview_dir / "report.md"
        result["extracted"] = extracted
        result["report"] = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    return result


@app.post("/api/interviews/{interview_id}/session-token")
def get_session_token(interview_id: str):
    interview_dir = INTERVIEWS_DIR / interview_id
    meta = read_json(interview_dir / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="Interview not found")
    if meta["status"] == "completed":
        raise HTTPException(status_code=409, detail="Interview already completed")

    config = read_json(CONFIG_FILE) or {}
    icp = config.get("icp") or "Not specified"
    hypotheses = config.get("hypotheses") or []

    try:
        client_secret = create_realtime_session(icp, hypotheses)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    meta["status"] = "in_progress"
    write_json(interview_dir / "meta.json", meta)

    return {"client_secret": client_secret}


@app.post("/api/interviews/{interview_id}/complete")
def complete_interview(interview_id: str, payload: CompletePayload):
    interview_dir = INTERVIEWS_DIR / interview_id
    meta = read_json(interview_dir / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="Interview not found")
    if meta["status"] == "completed":
        raise HTTPException(status_code=409, detail="Interview already completed")

    write_json(interview_dir / "transcript.json", payload.transcript)

    transcript_text = format_transcript(payload.transcript)
    hypotheses = (read_json(CONFIG_FILE) or {}).get("hypotheses") or []

    try:
        extracted = run_extraction(transcript_text, hypotheses)
    except Exception as e:
        extracted = {"error": str(e), "top_pain_points": [], "current_workflows": [],
                     "tools_mentioned": [], "hypothesis_assessment": []}
    write_json(interview_dir / "extracted.json", extracted)

    try:
        report = run_report(meta["name"], transcript_text, extracted)
    except Exception as e:
        report = f"# Interview Report: {meta['name']}\n\nReport generation failed: {e}\n\nRaw transcript saved."
    (interview_dir / "report.md").write_text(report, encoding="utf-8")

    meta["status"] = "completed"
    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(interview_dir / "meta.json", meta)

    return {"success": True}


# --- Insights route ---

@app.post("/api/insights")
def insights_qa(payload: InsightsPayload):
    completed = []
    for meta_file in INTERVIEWS_DIR.glob("*/meta.json"):
        meta = read_json(meta_file)
        if meta and meta.get("status") == "completed":
            extracted = read_json(meta_file.parent / "extracted.json")
            if extracted:
                completed.append({"name": meta["name"], "extracted": extracted})
    if not completed:
        raise HTTPException(status_code=400, detail="No completed interviews to query")
    try:
        answer = run_insights(payload.question, completed)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"answer": answer}


# --- Page routes ---

app.mount("/static", StaticFiles(directory="public"), name="static")


@app.get("/")
def dashboard():
    return FileResponse("public/dashboard.html")


@app.get("/interview/{interview_id}")
def interview_page(interview_id: str):
    return FileResponse("public/interview.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    print(f"Insight Loop running at http://localhost:{port}")
    print(f"Public URL: {os.getenv('BASE_URL', 'http://localhost:3000')}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
