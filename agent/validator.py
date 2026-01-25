import subprocess
import os

def validate(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=600,
            cwd=os.getcwd()
        )
        return result.returncode == 0
    except Exception:
        return False
