# validator.py
import os
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List

from patcher import apply_patch
from confidence import compute_confidence
from git_ops import create_pr
from llm import ask_llm
from cd_advisor import analyze_cd_failure

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
            cmd,
            capture_output=True,
            timeout=600,
            cwd=os.getcwd()
        )
        return result.returncode == 0
    except Exception:
        return False

# ------------------- CI Endpoint -------------------
@app.post("/ci", response_model=CIResponse)
def handle_ci(request: CIRequest):
    try:
        filename, code, command, confidence_score = ask_llm(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {e}")

    # Apply file changes
    apply_patch(filename, code)

    # Validate fix
    if not validate(command):
        raise HTTPException(status_code=400, detail="Fix failed validation")

    confidence = compute_confidence(validated=True, files_changed=1)

    # Create PR
    create_pr(filename, confidence)

    return CIResponse(
        status="PR_CREATED",
        error_type="dependency",  # You can adapt dynamically
        files_changed=[filename],
        confidence=confidence
    )

# ------------------- CD Endpoint -------------------
@app.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    explanation = analyze_cd_failure(request.log)
    return CDResponse(explanation=explanation)

# ------------------- Startup -------------------
if __name__ == "__main__":
    import uvicorn

    # Environment variable fallbacks
    os.environ.setdefault("GROQ_API_KEY", "<YOUR_GROQ_API_KEY>")
    os.environ.setdefault("GITHUB_REPOSITORY", "Kashish-0931/universal-ci-fix-agent")

    uvicorn.run(
        "validator:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
