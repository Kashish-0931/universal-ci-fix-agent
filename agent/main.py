from agent.parser import extract_failure
from agent.llm import ask_llm
from agent.patcher import apply_patch
from agent.validator import validate
from agent.confidence import compute_confidence
from agent.git_ops import create_pr
from agent.cd_advisor import analyze_cd_failure

failure_type, failure = extract_failure()

if not failure:
    print("No CI/CD failure detected")
    exit(0)

# ---------------- CI FLOW (UNCHANGED) ----------------
if failure_type == "ci":
    filename, code, failed_cmd,confidence  = ask_llm(failure)

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
