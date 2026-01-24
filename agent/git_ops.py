import subprocess
import time
import os

def create_pr(filename, confidence):
    branch = f"ai-fix-{int(time.time())}"

    subprocess.run(["git", "checkout", "-b", branch])
    subprocess.run(["git", "add", filename])
    subprocess.run([
        "git", "commit",
        "-m", f"AI CI/CD auto-fix (confidence: {confidence})"
    ])
    subprocess.run(["git", "push", "-u", "origin", branch])

    repo = os.environ["GITHUB_REPOSITORY"]
    print(f"""
PR CREATED
Confidence: {confidence}

https://github.com/{repo}/pull/new/{branch}
""")
