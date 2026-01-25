from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List

from llm import ask_llm
from patcher import apply_patch
from validator import validate
from confidence import compute_confidence
from git_ops import create_pr
from cd_advisor import analyze_cd_failure

app = FastAPI(title="Universal CI/CD LLM Agent")

# ---------------- Schemas ----------------

class CIRequest(BaseModel):
    log: str

class CIResponse(BaseModel):
    status: str
    error_type: str
    files_changed: List[str]
    confidence: float

class CDRequest(BaseModel):
    log: str

class CDResponse(BaseModel):
    explanation: str


@app.get("/")
def root():
    return {"message": "Universal CI/CD LLM Agent running"}


# ---------------- CI Endpoint ----------------

@app.post("/ci", response_model=CIResponse)
def handle_ci(request: CIRequest):
    try:
        result = ask_llm(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Apply file changes
    files = result["files_to_change"]
    for filename, content in files.items():
        apply_patch(filename, content)

    # Validate fix
    if not validate(result["command"]):
        raise HTTPException(
            status_code=400,
            detail="Fix failed validation"
        )

    confidence = compute_confidence(
        validated=True,
        files_changed=len(files)
    )

    # Create PR
    first_file = list(files.keys())[0]
    create_pr(first_file, confidence)

    return CIResponse(
        status="PR_CREATED",
        error_type=result["error_type"],
        files_changed=list(files.keys()),
        confidence=confidence
    )


# ---------------- CD Endpoint ----------------

@app.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    explanation = analyze_cd_failure(request.log)
    return CDResponse(explanation=explanation)
