import os
import subprocess
import requests
from openai import OpenAI

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

# ── Запрос к OpenAI ─────────────────────────────────────────────────────
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = f"""Ты — опытный Python разработчик. Проанализируй изменения в Pull Request.

СТАТИСТИКА ИЗМЕНЕНИЙ:
{diff_stat}

DIFF:
{diff_full}

Напиши ревью в формате Markdown со следующими разделами:
1. **📝 Описание изменений** — что было сделано (2-4 предложения)
2. **✅ Что сделано хорошо** — список сильных сторон
3. **⚠️ Потенциальные проблемы** — баги, уязвимости, нарушения best practices
4. **💡 Предложения по улучшению** — конкретные рекомендации
5. **🔢 Оценка** — от 1 до 10 с кратким обоснованием

Будь конкретен и лаконичен."""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1500,
)
review_text = response.choices[0].message.content

# ── Публикуем комментарий в PR ──────────────────────────────────────────
comment_body = f"""## 🤖 AI Code Review (GPT-4o mini)

{review_text}

---
<sub>Автоматическое ревью · коммит {head_sha[:7]}</sub>"""

repo = os.environ["REPO"]
pr_number = os.environ["PR_NUMBER"]
gh_token = os.environ["GH_TOKEN"]

response = requests.post(
    f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
    headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    },
    json={"body": comment_body},
)

if response.status_code == 201:
    print("✅ Комментарий успешно опубликован")
else:
    print(f"❌ Ошибка: {response.status_code} — {response.text}")
    exit(1)
import os
import subprocess
import requests
from openai import OpenAI

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

# ── Запрос к OpenAI ─────────────────────────────────────────────────────
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = f"""Ты — опытный Python разработчик. Проанализируй изменения в Pull Request.

СТАТИСТИКА ИЗМЕНЕНИЙ:
{diff_stat}

DIFF:
{diff_full}

Напиши ревью в формате Markdown со следующими разделами:
1. **📝 Описание изменений** — что было сделано (2-4 предложения)
2. **✅ Что сделано хорошо** — список сильных сторон
3. **⚠️ Потенциальные проблемы** — баги, уязвимости, нарушения best practices
4. **💡 Предложения по улучшению** — конкретные рекомендации
5. **🔢 Оценка** — от 1 до 10 с кратким обоснованием

Будь конкретен и лаконичен."""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1500,
)
review_text = response.choices[0].message.content

# ── Публикуем комментарий в PR ──────────────────────────────────────────
comment_body = f"""## 🤖 AI Code Review (GPT-4o mini)

{review_text}

---
<sub>Автоматическое ревью · коммит {head_sha[:7]}</sub>"""

repo = os.environ["REPO"]
pr_number = os.environ["PR_NUMBER"]
gh_token = os.environ["GH_TOKEN"]

response = requests.post(
    f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
    headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    },
    json={"body": comment_body},
)

if response.status_code == 201:
    print("✅ Комментарий успешно опубликован")
else:
    print(f"❌ Ошибка: {response.status_code} — {response.text}")
    exit(1)