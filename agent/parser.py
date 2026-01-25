from pathlib import Path

# Log file names
CI_LOG = "error.log"
CD_LOG = "deploy.log"

def extract_failure():
    """
    Checks for CI/CD failure logs.
    Returns exactly two values: (failure_type, failure_content)
    """
    if Path(CI_LOG).exists():
        return ("ci", Path(CI_LOG).read_text())

    if Path(CD_LOG).exists():
        return ("cd", Path(CD_LOG).read_text())

    return (None, None)
