
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from .llm import ask_llm
from .patcher import apply_patch
from .validator import validate
from .confidence import compute_confidence
from .git_ops import create_pr
from .cd_advisor import analyze_cd_failure

app2 = FastAPI(title="Universal CI/CD LLM Agent")

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

# ---------------- Root ----------------

@app.get("/")
def root():
    return {"message": "Universal CI/CD LLM Agent running"}

# ---------------- CI Endpoint ----------------

@app.post("/ci", response_model=CIResponse)
def handle_ci(request: CIRequest):
    try:
        # Correct unpacking of tuple
        filename, code, command, llm_confidence = ask_llm(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Apply patch
    apply_patch(filename, code)

    # Validate the applied fix
    if not validate(command):
        raise HTTPException(
            status_code=400,
            detail="Fix failed validation"
        )

    # Compute confidence
    confidence = compute_confidence(
        validated=True,
        files_changed=1
    )

    # Create PR
    create_pr(filename, confidence)

    return CIResponse(
        status="PR_CREATED",
        error_type="ci",  # fixed, since ask_llm tuple does not return error_type
        files_changed=[filename],
        confidence=confidence
    )

# ---------------- CD Endpoint ----------------

@app.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return CDResponse(explanation=explanation)
