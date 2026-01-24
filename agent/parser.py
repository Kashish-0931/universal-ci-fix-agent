from pathlib import Path

LOG_FILE = "error.log"

def extract_failure():
    if not Path(LOG_FILE).exists():
        return None
    return Path(LOG_FILE).read_text()
