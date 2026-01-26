
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
    filename, code, command, llm_confidence, suggested_fix = "unknown_file.py", "", [], 0.0, "No suggestion available"
    pr_url = ""
    
    try:
        # 1️⃣ Ask LLM for analysis
        try:
            llm_filename, llm_code, llm_command, llm_conf, llm_suggest = ask_llm(request.log)
            # Only overwrite defaults if LLM returned something valid
            if llm_filename:
                filename = llm_filename
                code = llm_code
                command = llm_command
                llm_confidence = llm_conf
                suggested_fix = llm_suggest or "Check the code for missing modules or typos"
        except Exception as e:
            print("LLM analysis failed:", e)
        
        # 2️⃣ Try to apply patch (do NOT overwrite filename/suggested_fix on failure)
        try:
            apply_patch(filename, code)
        except Exception as e:
            print("Patch failed:", e)
        
        # 3️⃣ Validate safely
        validated = False
        try:
            validated = validate(command)
        except Exception as e:
            print("Validation failed:", e)
        
        # 4️⃣ Compute confidence
        confidence = compute_confidence(validated=validated, files_changed=1)
        
        # 5️⃣ Attempt PR creation, but do not overwrite filename or suggested_fix
        try:
            pr_info = create_pr(filename, confidence)
            pr_url = pr_info.get("pr_url", "")
        except Exception as e:
            print("PR creation failed:", e)
        
        # 6️⃣ Return full info with suggested fix
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
            "suggested_fix": suggested_fix
        }



# ---------------- CD Endpoint ----------------

@app2.post("/cd", response_model=CDResponse)
def handle_cd(request: CDRequest):
    try:
        explanation = analyze_cd_failure(request.log)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return CDResponse(explanation=explanation)
