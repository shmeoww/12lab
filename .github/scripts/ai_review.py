import os
import subprocess
import requests

# ── Получаем diff PR ────────────────────────────────────────────────────
base_sha = os.environ["BASE_SHA"]
head_sha = os.environ["HEAD_SHA"]

result = subprocess.run(
    ["git", "diff", f"{base_sha}...{head_sha}", "--stat"],
    capture_output=True, text=True
)
diff_stat = result.stdout[:500]

result2 = subprocess.run(
    ["git", "diff", f"{base_sha}...{head_sha}"],
    capture_output=True, text=True
)
diff_full = result2.stdout[:15000]

# ── Запрос к Hugging Face ───────────────────────────────────────────────
hf_token = os.environ["HF_API_KEY"]

prompt = f"""You are an experienced Python developer. Review this Pull Request.

CHANGED FILES STAT:
{diff_stat}

DIFF:
{diff_full}

Write a code review in Markdown with these sections:
1. **📝 Description** — what was changed (2-4 sentences)
2. **✅ What is good** — list of strengths
3. **⚠️ Potential issues** — bugs, vulnerabilities, bad practices
4. **💡 Suggestions** — concrete recommendations
5. **🔢 Score** — from 1 to 10 with brief explanation"""

response = requests.post(
    "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.3/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {hf_token}",
        "Content-Type": "application/json",
    },
    json={
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7,
    },
    timeout=60,
)

if response.status_code != 200:
    print(f"❌ HF API error: {response.status_code} — {response.text}")
    exit(1)

data = response.json()
review_text = data["choices"][0]["message"]["content"]

# ── Публикуем комментарий в PR ──────────────────────────────────────────
comment_body = f"""## 🤖 AI Code Review (Mistral 7B)

{review_text}

---
<sub>Автоматическое ревью · коммит {head_sha[:7]}</sub>"""

repo = os.environ["REPO"]
pr_number = os.environ["PR_NUMBER"]
gh_token = os.environ["GH_TOKEN"]

resp = requests.post(
    f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
    headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    },
    json={"body": comment_body},
)

if resp.status_code == 201:
    print("✅ Комментарий успешно опубликован")
else:
    print(f"❌ Ошибка: {resp.status_code} — {resp.text}")
    exit(1)