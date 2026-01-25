from llm import ask_llm

def analyze_cd_failure(deploy_log: str):
    prompt = f"""
Deployment failed.

LOG:
{deploy_log}

TASK:
1. Identify root cause
2. Explain in simple terms
3. Suggest fixes (DO NOT modify code)

Return readable explanation.
"""

    return ask_llm(prompt)
