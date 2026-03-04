import json
import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI()

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
