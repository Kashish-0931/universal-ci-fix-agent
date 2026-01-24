from parser import extract_failure
from llm import ask_llm
from patcher import apply_patch
from validator import validate
from confidence import compute_confidence
from git_ops import create_pr

failure = extract_failure()
if not failure:
    print("No CI/CD failure detected")
    exit(0)

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
