
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
        try:
            filename, code, command, llm_confidence = ask_llm(request.log)
        except Exception as e:
            # Fallback if LLM fails
            filename, code, command, llm_confidence = "unknown_file.py", "", [], 0.0

        # Apply patch safely
        try:
            apply_patch(filename, code)
        except Exception:
            pass  # skip patch if fails

        # Validate safely
        validated = False
        try:
            validated = validate(command)
        except Exception:
            validated = False

        # Compute confidence
        confidence = compute_confidence(validated=validated, files_changed=1)

        # Create PR safely
        pr_url = ""
        try:
            pr_info = create_pr(filename, confidence)
            pr_url = pr_info.get("pr_url", "")
        except Exception:
            pr_url = ""

        # Return safe dict
        return {
            "status": "PR_CREATED" if pr_url else "PR_FAILED",
            "error_type": "ci",
            "files_changed": [filename] if filename else [],
            "confidence": confidence,
            "error_message": request.log,
            "file_path": filename,
            "line_number": 1,
            "pr_url": pr_url
        }

    except Exception as e:
        # Catch everything else
        return {
            "status": "ERROR",
            "error_type": "ci",
            "error_message": str(e),
            "files_changed": [],
            "confidence": 0.0
        }



# ---------------- CD Endpoint ----------------

@app2.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return CDResponse(explanation=explanation)
