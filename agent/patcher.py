from pathlib import Path

def apply_patch(filename, code):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"LLM suggested invalid file: {filename}")

    path.write_text(code)
