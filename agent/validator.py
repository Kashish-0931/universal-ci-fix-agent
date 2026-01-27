import os
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from .patcher import apply_patch
from .confidence import compute_confidence
from .git_ops import create_pr
from .llm import ask_llm
from .cd_advisor import analyze_cd_failure

# ------------------- FastAPI -------------------
app = FastAPI(title="Universal CI/CD LLM Agent")

# ------------------- Schemas -------------------
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

# ------------------- Helper -------------------
def validate(cmd):
    """Run a shell command and return True if successful."""
    try:
        if not cmd or len(cmd) == 0:
            return False
        result = subprocess.run(
            cmd, capture_output=True, timeout=600, cwd=os.getcwd()
        )
        return result.returncode == 0
    except Exception:
        return False

# ------------------- CI Endpoint -------------------
@app.post("/ci", response_model=CIResponse)
def handle_ci(request: CIRequest):
    try:
        filename, code, command, confidence_score, suggested_fix = ask_llm(request.log)
    except Exception as e:
        return CIResponse(
            status="ERROR",
            error_type="ci",
            files_changed=[],
            confidence=0.0
        )

    # Apply file changes safely
    try:
        apply_patch(filename, code)
    except Exception as e:
        print(f"Patch failed: {e}")
        filename, code = "<unchanged>", "<unchanged>"

    # Validate command
    validated = validate(command)
    if not validated:
        print("Fix did not pass validation")
        confidence_score = round(confidence_score * 0.5, 2)  # reduce confidence

    # Create PR if validated
    try:
        pr_info = create_pr(filename, confidence_score)
        pr_url = pr_info.get("pr_url", "")
    except Exception as e:
        print(f"PR creation failed: {e}")
        pr_url = ""

    return CIResponse(
        status="PR_CREATED" if pr_url else "SUGGESTION_READY",
        error_type="ci",
        files_changed=[filename] if filename else [],
        confidence=confidence_score
    )

# ------------------- CD Endpoint -------------------
@app.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return CDResponse(explanation=explanation)

# ------------------- Startup -------------------
if __name__ == "__main__":
    import uvicorn
    # Environment variable fallbacks
    os.environ.setdefault("GROQ_API_KEY", "<YOUR_GROQ_API_KEY>")
    os.environ.setdefault("GITHUB_REPOSITORY", "Kashish-0931/universal-ci-fix-agent")
    uvicorn.run("validator:app", host="0.0.0.0", port=8000, reload=True)

