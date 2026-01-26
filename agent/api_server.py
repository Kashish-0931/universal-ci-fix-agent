
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

@app2.get("/")
def root():
    return {"message": "Universal CI/CD LLM Agent running"}

# ---------------- CI Endpoint ----------------

@app2.post("/ci")
def handle_ci(request: CIRequest):
    try:
        # LLM analysis
        filename, code, command, llm_confidence = ask_llm(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Apply patch
    apply_patch(filename, code)

    # Validate fix
    if not validate(command):
        raise HTTPException(status_code=400, detail="Fix failed validation")

    # Compute confidence
    confidence = compute_confidence(validated=True, files_changed=1)

    # Create PR and get PR URL
    pr_info = create_pr(filename, confidence)
    pr_url = pr_info.get("pr_url", "")  # ensure create_pr returns dict with pr_url

    # Return full info
    return {
        "status": "PR_CREATED",
        "error_type": "ci",
        "files_changed": [filename],
        "confidence": confidence,
        "error_message": request.log,       # raw error log
        "file_path": filename,
        "line_number": 1,                   # you can improve by detecting line from LLM in future
        "pr_url": pr_url
    }


# ---------------- CD Endpoint ----------------

@app2.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return CDResponse(explanation=explanation)
