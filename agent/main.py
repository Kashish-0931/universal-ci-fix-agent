from parser import extract_failure
from llm import ask_llm
from patcher import apply_patch
from validator import validate
from confidence import compute_confidence
from git_ops import create_pr
from cd_advisor import analyze_cd_failure

failure_type, failure = extract_failure()

if not failure:
    print("No CI/CD failure detected")
    exit(0)

# ---------------- CI FLOW (UNCHANGED) ----------------
if failure_type == "ci":
    filename, code, failed_cmd = ask_llm(failure)

    apply_patch(filename, code)

    validated = validate(failed_cmd)
    if not validated:
        print("Fix did not pass validation")
        exit(1)

    confidence = compute_confidence(
        validated=True,
        files_changed=1
    )

    create_pr(filename, confidence)

# ---------------- CD FLOW (NEW) ----------------
elif failure_type == "cd":
    explanation = analyze_cd_failure(failure)
    print("\nCD FAILURE ANALYSIS:\n")
    print(explanation)
