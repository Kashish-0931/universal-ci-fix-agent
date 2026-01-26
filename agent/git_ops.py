import subprocess
import time
import os

def create_pr(filename, confidence):
    """
    Creates a Git branch, commits the file, pushes, and returns PR URL.
    Safe for CI/CD agent use.
    """
    try:
        # ensure env variable exists
        repo = os.environ.get("GITHUB_REPOSITORY")
        if not repo:
            raise EnvironmentError("GITHUB_REPOSITORY environment variable not set")

        # ensure GitHub token exists for authentication
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise EnvironmentError("GITHUB_TOKEN environment variable not set")

        branch = f"ai-fix-{int(time.time())}"

        # checkout new branch
        subprocess.run(
            ["git", "checkout", "-b", branch],
            check=True,
            capture_output=True,
            text=True,
            timeout=60
        )

        # stage file
        subprocess.run(
            ["git", "add", filename],
            check=True,
            capture_output=True,
            text=True,
            timeout=30
        )

        # commit changes
        subprocess.run(
            ["git", "commit", "-m", f"AI CI/CD auto-fix (confidence: {confidence})"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30
        )

        # push branch (use token in URL for CI/CD auth)
        remote_url = f"https://{github_token}@github.com/{repo}.git"
        subprocess.run(
            ["git", "push", "-u", remote_url, branch],
            check=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        pr_url = f"https://github.com/{repo}/pull/new/{branch}"

        # Optional: print info for logs
        print(f"""
PR CREATED SUCCESSFULLY
Confidence: {confidence}
Branch: {branch}
PR URL: {pr_url}
""")

        # Return the PR info
        return {"status": "success", "pr_url": pr_url, "branch": branch}

    except subprocess.CalledProcessError as e:
        return {"status": "error", "step": "git_command", "message": e.stderr}
    except subprocess.TimeoutExpired as e:
        return {"status": "error", "step": "timeout", "message": str(e)}
    except Exception as e:
        return {"status": "error", "step": "exception", "message": str(e)}
