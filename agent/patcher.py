
from pathlib import Path

def apply_patch(filename, content):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n")
