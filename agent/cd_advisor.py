from .llm import ask_llm

def analyze_cd_failure(deploy_log: str):
    """
    Analyze a CD/deployment log and return a human-readable explanation.
    """
    SYSTEM_PROMPT = """
You are a CI/CD expert.

TASK:
1. Identify root cause of deployment failure.
2. Explain in simple terms.
3. Suggest safe fixes.
Do NOT modify any code.
Return a readable explanation.
"""
    response = ask_llm(
        deploy_log,
        system_prompt=SYSTEM_PROMPT,
        expect_json=False  # important: return plain text
    )

    return response.strip()
