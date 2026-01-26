import subprocess
import time
import os

def create_pr(filename, confidence):
    try:
        repo = os.environ["GITHUB_REPOSITORY"]
        token = os.environ["GITHUB_TOKEN"]

        # REQUIRED for CI
        subprocess.run(
            ["git", "config", "--global", "user.name", "ci-agent"],
            check=True
        )
        subprocess.run(
            ["git", "config", "--global", "user.email", "ci-agent@users.noreply.github.com"],
            check=True
        )

        branch = f"ai-fix-{int(time.time())}"

        subprocess.run(["git", "checkout", "-b", branch], check=True)
        subprocess.run(["git", "add", filename], check=True)

        subprocess.run(
            ["git", "commit", "-m", f"AI CI/CD auto-fix (confidence: {confidence})"],
            check=True
        )

        remote = f"https://{token}@github.com/{repo}.git"
        subprocess.run(["git", "push", "-u", remote, branch], check=True)

        pr_url = f"https://github.com/{repo}/pull/new/{branch}"

        return {
            "status": "success",
            "branch": branch,
            "pr_url": pr_url
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
