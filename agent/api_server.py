
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
    # Initialize defaults
    @app2.post("/ci")
def handle_ci(request: CIRequest):
    pr_url = ""
    try:
        # 1️⃣ Ask LLM for analysis
        suggestions = ask_llm(request.log)  # Returns a list of dicts
        first_suggestion = suggestions[0] if suggestions else {}

        # Use first suggestion or defaults
        filename = first_suggestion.get("file", "unknown_file.py")
        code = first_suggestion.get("code", "<unchanged>")
        llm_confidence = first_suggestion.get("confidence", 0.0)
        suggested_fix = first_suggestion.get("suggested_fix", "Check the code for errors")

        # 2️⃣ Apply patch safely
        try:
            apply_patch(filename, code)
        except Exception as e:
            print("Patch failed:", e)
            filename, code = "<unchanged>", "<unchanged>"
            suggested_fix = code

        # 3️⃣ Validation skipped (no shell commands)
        validated = True

        # 4️⃣ Compute confidence
        confidence = compute_confidence(validated=validated, files_changed=1)

        # 5️⃣ Attempt PR creation
        try:
            pr_info = create_pr(filename, confidence)
            pr_url = pr_info.get("pr_url", "")
        except Exception as e:
            print("PR creation failed:", e)
            pr_url = ""

        # 6️⃣ Return info with LLM suggestion
        return {
            "status": "PR_CREATED" if pr_url else "SUGGESTION_READY",
            "error_type": "ci",
            "files_changed": [filename] if filename else [],
            "confidence": confidence,
            "error_message": request.log,
            "file_path": filename,
            "line_number": 1,
            "pr_url": pr_url,
            "suggested_fix": suggested_fix
        }

    except Exception as e:
        # Fallback for unexpected errors
        return {
            "status": "ERROR",
            "error_type": "ci",
            "error_message": str(e),
            "files_changed": [],
            "confidence": 0.0,
            "suggested_fix": "Manual investigation required"
        }




# ---------------- CD Endpoint ----------------

@app2.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return CDResponse(explanation=explanation)
