import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ------------------ Helpers ------------------

def extract_file(error_log: str):
    """Extract file path from traceback if present"""
    m = re.search(r'File "([^"]+)"', error_log)
    return m.group(1) if m else "<unknown>"

def extract_missing_module(error_log: str):
    """Detect missing module/package in any language"""
    m = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    if m:
        return m.group(1)
    m = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", error_log)  # Node.js
    if m:
        return m.group(1)
    return None

def extract_nameerror_details(error_log: str):
    """Detect undefined variable or function"""
    m = re.search(r"NameError: name '([^']+)' is not defined", error_log)
    if m:
        undefined_name = m.group(1)
        suggestion_match = re.search(r"Did you mean: '([^']+)'", error_log)
        suggested_name = suggestion_match.group(1) if suggestion_match else "<unknown>"
        return undefined_name, suggested_name
    return None, None

def extract_permission_file(error_log: str):
    m = re.search(r"PermissionError: \[Errno \d+\] .*: '([^']+)'", error_log)
    return m.group(1) if m else None

# ------------------ Main ------------------

def ask_llm(error_log: str):
    """
    Universal CI/CD error suggester.
    Returns a list of suggestions.
    Each suggestion: file, code, commands, confidence, suggested_fix
    """

    system_prompt = """
You are a universal CI/CD error fixing agent.
TASK:
- Analyze any error log (Python, Node.js, Java, Go, Rust, shell, Docker, YAML, JSON, CI/CD)
- Always provide at least one safe suggested fix
- Never suggest destructive commands
- Return JSON array of suggestions with keys:
  file, code, commands, confidence, suggested_fix
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"ERROR LOG:\n{error_log}"}
            ]
        )
        raw = response.choices[0].message.content.strip()
        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            raise ValueError
    except Exception:
        # fallback generic suggestion
        suggestions = [{
            "file": extract_file(error_log),
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.5,
            "suggested_fix": "Manual investigation required"
        }]

    # ------------------ Auto heuristics for common errors ------------------

    result = []

    # Missing module/package
    missing_module = extract_missing_module(error_log)
    if missing_module:
        result.append({
            "file": "package/dependency list",
            "code": "<update dependency file>",
            "commands": [],
            "confidence": 1.0,
            "suggested_fix": f"Install or add missing package/module: {missing_module}"
        })

    # NameError / ReferenceError
    if "NameError" in error_log or "ReferenceError" in error_log:
        undefined_name, suggested_name = extract_nameerror_details(error_log)
        result.append({
            "file": extract_file(error_log),
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.7,
            "suggested_fix": f"Undefined variable/function: {undefined_name}. Did you mean: {suggested_name}"
        })

    # PermissionError
    if "PermissionError" in error_log or "EACCES" in error_log:
        file = extract_permission_file(error_log) or extract_file(error_log)
        result.append({
            "file": file,
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.8,
            "suggested_fix": "Fix file/directory permissions in CI environment"
        })

    # YAML/JSON config errors
    if "YAMLError" in error_log or "JSONDecodeError" in error_log or ".yml" in error_log or ".json" in error_log:
        result.append({
            "file": extract_file(error_log),
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.8,
            "suggested_fix": "Fix syntax in YAML/JSON configuration files"
        })

    # Version mismatch errors
    if re.search(r"version mismatch|unsupported version", error_log, re.IGNORECASE):
        result.append({
            "file": "<unchanged>",
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.9,
            "suggested_fix": "Align language/runtime version in CI workflow"
        })

    # Shell / CI/CD command errors
    if "command not found" in error_log.lower() or "exit code" in error_log.lower() or "bash:" in error_log.lower():
        result.append({
            "file": "<ci_pipeline>",
            "code": "<unchanged>",
            "commands": [],
            "confidence": 0.7,
            "suggested_fix": "Check shell commands, tool installation, environment variables, or CI pipeline"
        })

    # fallback to LLM suggestion if nothing else
    if not result:
        result.append({
            "file": extract_file(error_log),
            "code": "<unchanged>",
            "commands": [],
            "confidence": float(suggestions[0].get("confidence", 0.6)),
            "suggested_fix": suggestions[0].get("suggested_fix", "Manual investigation required")
        })

    return result
