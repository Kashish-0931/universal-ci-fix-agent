import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ------------------ Helpers ------------------

def extract_traceback_file(error_log: str):
    m = re.search(r'File "([^"]+)"', error_log)
    return m.group(1) if m else None

def extract_missing_module(error_log: str):
    m = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_log)
    return m.group(1) if m else None

def extract_missing_file(error_log: str):
    m = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]", error_log)
    return m.group(1) if m else None

# ------------------ Main ------------------

def ask_llm(error_log: str, system_prompt: str = None, expect_json: bool = True):
    """
    Returns:
    filename, code, commands, confidence, suggested_fix
    """

    if system_prompt is None:
        system_prompt = """
You are a CI/CD error classification agent.

TASK:
Classify the error and explain it clearly.

DO NOT:
- invent files
- suggest commands
- suggest fixes

Return STRICT JSON only.

Schema:
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

    error_type = data.get("error_type", "")
    confidence = float(data.get("confidence", 0.6))

    # ==========================================================
    # 🔹 AUTO-FIXABLE ERRORS
    # ==========================================================

    # 1. Missing Python dependency
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

    # 2. Missing file
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

    # 3. Permission issue
    if error_type == "PermissionError":
        file = extract_traceback_file(error_log)
        return (
            file or "<unchanged>",
            "<unchanged>",
            [],
            0.8,
            "Fix file permissions in CI environment"
        )

    # 4. Python version issue
    if "python version" in error_log.lower():
        return (
            "<unchanged>",
            "<unchanged>",
            [],
            0.9,
            "Align Python version in CI workflow (uses/setup-python)"
        )

    # 5. YAML / JSON config errors
    if error_type in ("YAMLError", "JSONDecodeError"):
        file = extract_traceback_file(error_log)
        return (
            file or "<unchanged>",
            "<unchanged>",
            [],
            0.8,
            "Fix syntax error in configuration file"
        )

    # ==========================================================
    # 🔸 NON-DETERMINISTIC (SUGGEST ONLY)
    # ==========================================================

    traceback_file = extract_traceback_file(error_log)

    return (
        traceback_file or "<unchanged>",
        "<unchanged>",
        [],
        confidence,
        data.get("fix_explanation", "Manual investigation required")
    )

