import subprocess

def validate(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=600
        )
        return result.returncode == 0
    except Exception:
        return False
