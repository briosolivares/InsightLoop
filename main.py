import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

app = FastAPI()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
INTERVIEWS_DIR = DATA_DIR / "interviews"

# Ensure data directories exist on startup
DATA_DIR.mkdir(exist_ok=True)
INTERVIEWS_DIR.mkdir(exist_ok=True)


# --- File helpers ---

def read_json(filepath: Path) -> dict | None:
    try:
        data = json.loads(filepath.read_text())
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_json_list(filepath: Path) -> list | None:
    try:
        data = json.loads(filepath.read_text())
        return data if isinstance(data, list) else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(filepath: Path, data: dict | list) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- Config API ---

class ConfigPayload(BaseModel):
    icp: str | None = None
    hypotheses: list[str] | None = None


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


# --- Interview API ---

class InterviewPayload(BaseModel):
    name: str
    notes: str | None = None


@app.post("/api/interviews", status_code=201)
def create_interview(payload: InterviewPayload):
    interview_id = str(uuid4())
    url = f"{BASE_URL}/interview/{interview_id}"
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


# --- Session token + interview lifecycle ---

SYSTEM_PROMPT_TEMPLATE  = Path("prompts/interview_system.txt").read_text(encoding="utf-8")
EXTRACT_PROMPT_TEMPLATE = Path("prompts/extract_insights.txt").read_text(encoding="utf-8")
REPORT_PROMPT_TEMPLATE  = Path("prompts/generate_report.txt").read_text(encoding="utf-8")


def format_transcript(transcript: list) -> str:
    lines = []
    for turn in transcript:
        role = "Interviewer" if turn.get("role") == "assistant" else "Interviewee"
        lines.append(f"{role}: {turn.get('content', '').strip()}")
    return "\n".join(lines)


def parse_json_response(text: str) -> dict:
    """Parse JSON from model response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def fill_template(template: str, **kwargs) -> str:
    """Safe template fill using replace() — avoids .format() choking on JSON braces in templates."""
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", value)
    return result


def run_extraction(transcript_text: str, hypotheses: list) -> dict:
    hypotheses_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hypotheses)) or "None provided"
    prompt = fill_template(EXTRACT_PROMPT_TEMPLATE, hypotheses=hypotheses_text, transcript=transcript_text)
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json_response(response.choices[0].message.content)


def run_report(name: str, transcript_text: str, extracted: dict) -> str:
    prompt = fill_template(
        REPORT_PROMPT_TEMPLATE,
        name=name,
        transcript=transcript_text,
        extracted=json.dumps(extracted, indent=2),
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


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
    hypotheses_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hypotheses)) or "None provided"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(icp=icp, hypotheses=hypotheses_text)

    api_key = os.getenv("OPENAI_API_KEY")
    payload = json.dumps({
        "model": "gpt-4o-realtime-preview",
        "modalities": ["audio", "text"],
        "voice": "alloy",
        "instructions": system_prompt,
        "input_audio_transcription": {"model": "whisper-1"},
        "turn_detection": {"type": "server_vad"},
        "tools": [{
            "type": "function",
            "name": "finish_interview",
            "description": "Call this when you have covered all hypotheses and are ready to end the interview.",
            "parameters": {"type": "object", "properties": {}},
        }],
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/realtime/sessions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            session_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e.read().decode()}")

    meta["status"] = "in_progress"
    write_json(interview_dir / "meta.json", meta)

    return {"client_secret": session_data["client_secret"]["value"]}


class CompletePayload(BaseModel):
    transcript: list


@app.post("/api/interviews/{interview_id}/complete")
def complete_interview(interview_id: str, payload: CompletePayload):
    interview_dir = INTERVIEWS_DIR / interview_id
    meta = read_json(interview_dir / "meta.json")
    if not meta:
        raise HTTPException(status_code=404, detail="Interview not found")
    if meta["status"] == "completed":
        raise HTTPException(status_code=409, detail="Interview already completed")

    # Save raw transcript
    write_json(interview_dir / "transcript.json", payload.transcript)

    transcript_text = format_transcript(payload.transcript)
    config = read_json(CONFIG_FILE) or {}
    hypotheses = config.get("hypotheses") or []

    # GPT-4o call 1: structured extraction
    try:
        extracted = run_extraction(transcript_text, hypotheses)
    except Exception as e:
        extracted = {"error": str(e), "top_pain_points": [], "current_workflows": [],
                     "tools_mentioned": [], "hypothesis_assessment": []}
    write_json(interview_dir / "extracted.json", extracted)

    # GPT-4o call 2: markdown report
    try:
        report = run_report(meta["name"], transcript_text, extracted)
    except Exception as e:
        report = f"# Interview Report: {meta['name']}\n\nReport generation failed: {e}\n\nRaw transcript saved."
    (interview_dir / "report.md").write_text(report, encoding="utf-8")

    # Mark completed
    meta["status"] = "completed"
    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(interview_dir / "meta.json", meta)

    return {"success": True}


# --- Static files + SPA routes ---

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
    print(f"Public URL: {BASE_URL}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
