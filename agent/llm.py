import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ------------------ Helpers ------------------

def extract_traceback_file(error_log: str):
    m = re.search(r'File "([^"]+)"', error_log)
    return m.group(1) if m else "<unknown>"

def extract_missing_module(error_log: str):
    m = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    return m.group(1) if m else None

def extract_missing_file(error_log: str):
    m = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]", error_log)
    return m.group(1) if m else None

def extract_nameerror_details(error_log: str):
    m = re.search(r"NameError: name '([^']+)' is not defined", error_log)
    if m:
        undefined_name = m.group(1)
        suggestion_match = re.search(r"Did you mean: '([^']+)'", error_log)
        suggested_name = suggestion_match.group(1) if suggestion_match else "<unknown>"
        return undefined_name, suggested_name
    return None, None

# ------------------ Main ------------------

def ask_llm(error_log: str, system_prompt: str = None, expect_json: bool = True):
    """
    Returns:
    filename, code, commands, confidence, suggested_fix
    """

    if system_prompt is None:
        system_prompt = """
You are a CI/CD error fixing agent.

TASK:
- Analyze the error log
- Always provide a suggested fix
- Safe minimal changes only
- Do not invent dangerous commands or files

Return JSON only:
{
  "error_type": "string",
  "error_detected": "string",
  "root_cause": "string",
  "fix_explanation": "string",
  "confidence": number
}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ERROR LOG:\n{error_log}"}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("\nRAW LLM OUTPUT:\n", raw)

    if not expect_json:
        return raw

    data = json.loads(raw)

    error_type = data.get("error_type", "UnknownError")
    confidence = float(data.get("confidence", 0.6))

    # ------------------ AUTO-FIXABLE ------------------

    # ModuleNotFoundError / ImportError
    if error_type in ("ModuleNotFoundError", "ImportError"):
        missing = extract_missing_module(error_log)
        if missing:
            return (
                "requirements.txt",
                f"{missing}\n",
                [],
                1.0,
                f"Add '{missing}' to requirements.txt"
            )

    # FileNotFoundError
    if error_type == "FileNotFoundError":
        missing_file = extract_missing_file(error_log)
        if missing_file:
            return (
                missing_file,
                "",
                [],
                0.9,
                f"Create missing file: {missing_file}"
            )

    # PermissionError
    if error_type == "PermissionError":
        file = extract_traceback_file(error_log)
        return (
            file,
            "<unchanged>",
            [],
            0.8,
            "Fix file permissions in CI environment"
        )

    # NameError: always suggest
    if error_type == "NameError":
        undefined_name, suggested_name = extract_nameerror_details(error_log)
        suggested_fix = (f"Function or variable name mismatch: {suggested_name} vs {undefined_name}"
                         if undefined_name else "Check undefined name in code")
        return (
            extract_traceback_file(error_log),
            "<unchanged>",
            [],
            0.7,
            suggested_fix
        )

    # YAML/JSON errors
    if error_type in ("YAMLError", "JSONDecodeError"):
        file = extract_traceback_file(error_log)
        return (
            file,
            "<unchanged>",
            [],
            0.8,
            "Fix syntax error in configuration file"
        )

    # Python version errors
    if "python version" in error_log.lower():
        return (
            "<unchanged>",
            "<unchanged>",
            [],
            0.9,
            "Align Python version in CI workflow (uses/setup-python)"
        )

    # ------------------ FALLBACK: always suggest ------------------
    suggested_fix = data.get("fix_explanation", "Manual investigation required")
    return (
        extract_traceback_file(error_log),
        "<unchanged>",
        [],
        confidence,
        suggested_fix
    )
