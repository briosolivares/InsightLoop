import json
import os
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT_TEMPLATE  = Path("prompts/interview_system.txt").read_text(encoding="utf-8")
EXTRACT_PROMPT_TEMPLATE = Path("prompts/extract_insights.txt").read_text(encoding="utf-8")
REPORT_PROMPT_TEMPLATE  = Path("prompts/generate_report.txt").read_text(encoding="utf-8")
INSIGHTS_QA_TEMPLATE    = Path("prompts/insights_qa.txt").read_text(encoding="utf-8")


# --- Template + parsing helpers ---

def fill_template(template: str, **kwargs) -> str:
    """Safe template substitution — uses replace() to avoid .format() choking on JSON braces."""
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", value)
    return result


def parse_json_response(text: str) -> dict:
    """Parse JSON from a model response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def format_transcript(transcript: list) -> str:
    """Convert transcript array to readable Interviewer/Interviewee text for prompts."""
    lines = []
    for turn in transcript:
        role = "Interviewer" if turn.get("role") == "assistant" else "Interviewee"
        lines.append(f"{role}: {turn.get('content', '').strip()}")
    return "\n".join(lines)


# --- OpenAI Realtime session ---

def create_realtime_session(icp: str, hypotheses: list) -> str:
    """
    Creates an OpenAI Realtime session configured with the interview system prompt.
    Returns the ephemeral client_secret for the browser to use with WebRTC.
    """
    hypotheses_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hypotheses)) or "None provided"
    system_prompt = fill_template(SYSTEM_PROMPT_TEMPLATE, icp=icp, hypotheses=hypotheses_text)

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
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            session_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI Realtime API error: {e.read().decode()}")

    return session_data["client_secret"]["value"]


# --- Post-interview processing ---

def run_extraction(transcript_text: str, hypotheses: list) -> dict:
    """
    Calls GPT-4o to extract structured insights from the transcript.
    Returns a dict matching the extracted.json schema.
    """
    hypotheses_text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(hypotheses)) or "None provided"
    prompt = fill_template(EXTRACT_PROMPT_TEMPLATE, hypotheses=hypotheses_text, transcript=transcript_text)
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json_response(response.choices[0].message.content)


def run_insights(question: str, interviews: list) -> str:
    """
    Calls GPT-4o to answer a cross-interview question.
    interviews: list of dicts with keys: name, extracted (dict)
    Returns the answer as a plain string.
    """
    context_parts = []
    for iv in interviews:
        extracted = iv["extracted"]
        name = iv["name"]
        pain_points = "\n".join(f"  - {p}" for p in extracted.get("top_pain_points", []))
        workflows = "\n".join(f"  - {w}" for w in extracted.get("current_workflows", []))
        tools = ", ".join(extracted.get("tools_mentioned", [])) or "None"
        assessments = []
        for h in extracted.get("hypothesis_assessment", []):
            quotes = "; ".join(f'"{q}"' for q in h.get("evidence_quotes", []))
            assessments.append(f"  - {h.get('hypothesis')} → {h.get('status')}" + (f" ({quotes})" if quotes else ""))
        hypotheses_text = "\n".join(assessments) or "  None"
        context_parts.append(
            f"### {name}\n"
            f"Pain points:\n{pain_points or '  None'}\n"
            f"Current workflows:\n{workflows or '  None'}\n"
            f"Tools mentioned: {tools}\n"
            f"Hypothesis assessments:\n{hypotheses_text}"
        )
    context = "\n\n".join(context_parts)
    prompt = fill_template(
        INSIGHTS_QA_TEMPLATE,
        interview_count=str(len(interviews)),
        context=context,
        question=question,
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def run_report(name: str, transcript_text: str, extracted: dict) -> str:
    """
    Calls GPT-4o to generate a human-readable markdown report.
    Returns the report as a markdown string.
    """
    prompt = fill_template(
        REPORT_PROMPT_TEMPLATE,
        name=name,
        transcript=transcript_text,
        extracted=json.dumps(extracted, indent=2),
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
