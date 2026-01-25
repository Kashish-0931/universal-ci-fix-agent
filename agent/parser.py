from pathlib import Path

CI_LOG = "error.log"
CD_LOG = "deploy.log"

def extract_failure():
    if Path(CI_LOG).exists():
        return "ci", Path(CI_LOG).read_text()

    if Path(CD_LOG).exists():
        return "cd", Path(CD_LOG).read_text()

    return None, None
