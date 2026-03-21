"""FastAPI backend for EDI parser with Gemini AI explanations."""

import os
import time

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from parser import parse_edi


def _shorten(text: str | None, limit: int = 240) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _normalize_model_name(name: str) -> str:
    value = (name or "").strip().strip("'").strip('"')
    if value.startswith("models/"):
        return value.split("/", 1)[1]
    return value


def configure_gemini() -> None:
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)


app = FastAPI(title="EDI Parser API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://edilens-2.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    raw: str
    complete_parse: bool = False


class ExplainRequest(BaseModel):
    type: str  # "segment" or "error"
    segment: str
    elements: list[str] | None = None
    raw: str | None = None
    error: str | None = None


@app.post("/parse")
async def parse(request: ParseRequest):
    """Parse raw EDI text into structured segments."""
    result = parse_edi(request.raw, complete_parse=request.complete_parse)
    return result


@app.post("/explain")
async def explain(request: ExplainRequest):
    """Get AI explanation for a segment or error using Gemini."""
    try:
        configure_gemini()
    except HTTPException:
        raise

    if request.type == "segment":
        prompt = f"""You are an EDI assistant for healthcare claims.
Explain this X12 segment in plain English with helpful context.
Response format:
1) What this segment generally means in healthcare billing (1 short sentence).
2) What these specific values indicate (2-3 short bullet points).
3) Why it matters or what to check next (1 short sentence).
Keep it concise but not overly terse.

Segment: {request.segment}
Elements: {(request.elements or [])[:12]}
Raw: {_shorten(request.raw, 220)}"""
    elif request.type == "error":
        prompt = f"""You are an EDI assistant for healthcare claims.
Explain this parsing issue with short context.
Response format:
1) What this error means.
2) Most likely cause in an EDI file.
3) One practical fix and what to verify after fixing.
Keep it concise.

Segment: {request.segment}
Error: {_shorten(request.error, 160)}"""
    else:
        raise HTTPException(status_code=400, detail="type must be 'segment' or 'error'")

    model_candidates = [
        _normalize_model_name(os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")),
        "gemini-flash-lite-latest",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest",
        "gemini-2.0-flash",
    ]
    # Preserve order and remove duplicates.
    deduped_models: list[str] = []
    for name in model_candidates:
        normalized = _normalize_model_name(name)
        if normalized and normalized not in deduped_models:
            deduped_models.append(normalized)

    last_error = ""
    for model_name in deduped_models:
        retry_count = 0
        try:
            import google.generativeai as genai

            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": 160, "temperature": 0.2},
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text and getattr(response, "candidates", None):
                parts: list[str] = []
                for candidate in response.candidates:
                    content = getattr(candidate, "content", None)
                    if not content:
                        continue
                    for part in getattr(content, "parts", []):
                        part_text = getattr(part, "text", None)
                        if part_text:
                            parts.append(part_text)
                text = "\n".join(parts).strip()
            if not text:
                text = "No explanation returned by Gemini for this input."
            return {"explanation": text, "model": model_name}
        except Exception as e:
            last_error = str(e)
            if "429" in last_error and retry_count < 1:
                retry_count += 1
                time.sleep(2)
                try:
                    import google.generativeai as genai

                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(
                        prompt,
                        generation_config={"max_output_tokens": 160, "temperature": 0.2},
                    )
                    text = (getattr(response, "text", None) or "").strip()
                    if text:
                        return {"explanation": text, "model": model_name}
                except Exception as retry_error:
                    last_error = str(retry_error)
            # If model not found/supported, retry with next candidate.
            if "not found" in last_error.lower() or "not supported" in last_error.lower():
                continue
            if "429" in last_error:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Gemini free-tier quota exceeded. Wait and retry, or set GEMINI_MODEL="
                        "gemini-flash-lite-latest in backend/.env."
                    ),
                )
            break

    raise HTTPException(
        status_code=500,
        detail=f"Gemini API error: {last_error}. Try setting GEMINI_MODEL in backend/.env.",
    )
