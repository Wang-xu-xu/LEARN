"""
语音管家 — DeepSeek 大模型查询模块
支持自然语言问答，通过 DeepSeek API 调用
"""

import os
import json
import urllib.request
import urllib.error

# API 配置 — 通过环境变量 DEEPSEEK_API_KEY 设置
API_URL = "https://api.deepseek.com/chat/completions"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一个电脑语音管家，通过语音与用户交互。
回答要求：
1. 简洁直接，控制在 2-4 句话以内
2. 口语化，适合朗读
3. 如果需要分步骤说明，列出清晰要点"""


def query_deepseek(prompt: str, max_tokens: int = 400) -> str:
    """调用 DeepSeek API 进行问答"""
    if not API_KEY:
        return "未配置 DeepSeek API 密钥，请设置环境变量 DEEPSEEK_API_KEY"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            return "API 密钥无效，请检查 DEEPSEEK_API_KEY"
        return f"API 请求失败 ({e.code})"
    except Exception as e:
        return f"查询超时，请稍后重试"
