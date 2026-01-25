import subprocess
import time
import os

def create_pr(filename, confidence):
    branch = f"ai-fix-{int(time.time())}"

    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", filename], check=True)
    subprocess.run([
        "git", "commit",
        "-m", f"AI CI/CD auto-fix (confidence: {confidence})"
    ], check=True)
    subprocess.run(["git", "push", "-u", "origin", branch], check=True)

    repo = os.environ["GITHUB_REPOSITORY"]

    print(f"""
PR CREATED
Confidence: {confidence}

https://github.com/{repo}/pull/new/{branch}
""")
