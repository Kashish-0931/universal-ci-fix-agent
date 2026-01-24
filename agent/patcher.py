from pathlib import Path

def apply_patch(filename, code):
    Path(filename).write_text(code)
