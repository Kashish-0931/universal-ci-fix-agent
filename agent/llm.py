import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

def ask_llm(error_log: str):
    prompt = f"""
CI/CD failed.

ERROR LOG:
{error_log}

TASK:
1. Identify the failing command
2. Fix the issue
3. Output EXACTLY:

filename:<file>
command:<command as python list>
<full corrected code>
"""

    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    lines = r.choices[0].message.content.strip().splitlines()

    filename = lines[0].replace("filename:", "").strip()
    command = eval(lines[1].replace("command:", "").strip())
    code = "\n".join(lines[2:])

    return filename, code, command
