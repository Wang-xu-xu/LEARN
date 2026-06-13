"""
联网搜索模块 v2 — 多重降级 + 智能清洗 + 精简摘要
"""
import re, time, html as _html
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeout
from ddgs import DDGS

TIMEOUT = 8
MAX_RETRIES = 2

# 抓取用 UA 池，降低反爬概率
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def _clean_snippet(text):
    """清洗搜索摘要：去HTML实体/标签/多余空白"""
    if not text: return ""
    text = _html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)          # 去HTML标签
    text = re.sub(r"\s+", " ", text).strip()      # 合并空白
    text = re.sub(r"…+", "，", text)              # 省略号换逗号
    return text


def _retry(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """通用重试包装"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.8 * (attempt + 1))
    print(f"[搜索] 重试{max_retries}次后仍失败: {last_err}")
    return None


def search_web(query, num=5):
    """
    DDGS 搜索，降级方案都内聚在此。
    返回 [(title, url, snippet), ...]，失败返回空列表。
    """
    # 方案1：DDGS API
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num, region="cn-zh"))
        items = []
        for r in results:
            title = (r.get("title") or "").strip()
            url = (r.get("href") or "").strip()
            body = _clean_snippet(r.get("body", ""))
            if title or body:
                items.append((title, url, body))
        if items:
            return items
    except Exception as e:
        print(f"[搜索] DDGS 失败: {e}")

    # 方案2：Bing 备用（轻量HTML抓取）
    try:
        import urllib.request, urllib.parse
        from html.parser import HTMLParser
        q = urllib.parse.quote(query)
        req = urllib.request.Request(
            f"https://www.bing.com/search?q={q}&setlang=zh-cn",
            headers={"User-Agent": UA_POOL[0]}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
        # 简易提取搜索结果
        items = []
        for m in re.finditer(r'<li class="b_algo"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_text, re.DOTALL):
            url = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            # 找摘要
            snippet_match = re.search(r'(?:class="b_caption"[^>]*>.*?<p[^>]*>|<div class="b_attribution".*?</div>\s*)(.*?)(?:</p>|</div>)', html_text[m.end():m.end()+2000], re.DOTALL)
            snippet = ""
            if snippet_match:
                snippet = _clean_snippet(snippet_match.group(1))
            if title:
                items.append((title, url, snippet))
        if items:
            print(f"[搜索] Bing 备用成功, {len(items)} 条")
            return items[:num]
    except Exception as e:
        print(f"[搜索] Bing 备用也失败: {e}")

    return []


def fetch_page(url, index=0):
    """抓取网页正文，自动轮换UA"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            import requests
            from bs4 import BeautifulSoup
            ua = UA_POOL[(index + attempt) % len(UA_POOL)]
            resp = requests.get(url, headers={"User-Agent": ua}, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code >= 400:
                continue
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]
            return "\n".join(lines)[:2500]
        except:
            if attempt < MAX_RETRIES:
                time.sleep(0.6)
    return ""


def _extract_key_sentences(text, max_sentences=3, min_len=8):
    """提取关键句子：过滤短句/导航/噪声，保留前N句"""
    sentences = re.split(r"[。！？；\n]", text)
    result = []
    for s in sentences:
        s = s.strip()
        if len(s) < min_len: continue
        # 跳过明显的导航/菜单文本
        if re.match(r"^(首页|登录|注册|关于|更多|搜索|菜单|导航|版权所有|©)\s*$", s):
            continue
        # 跳过纯数字/符号
        if re.match(r"^[\d\s\.\,\-／]+$", s):
            continue
        result.append(s)
        if len(result) >= max_sentences:
            break
    return "。".join(result)


def smart_search(query, max_results=3):
    """一步到位：搜索 → 清洗 → 提取 → 返回精准摘要"""
    print(f"[搜索] {query}")
    items = _retry(search_web, query, num=max_results + 2) or []

    if not items:
        return {"answer": f"搜索「{query}」没有结果", "sources": []}

    # 第一阶段：搜索摘要已经相当丰富，先做清洗和关键句提取
    snippets = [_clean_snippet(s) for _, _, s in items if s]
    quick_answer = ""
    if snippets:
        combined = "；".join(snippets[:3])
        quick_answer = _extract_key_sentences(combined, max_sentences=3, min_len=6)

    # 第二阶段：仅在摘要不足（<50字）时抓取网页
    sources = [(t, u) for t, u, _ in items[:max_results] if u.startswith("http")]

    if quick_answer and len(quick_answer) >= 50:
        return {"answer": quick_answer[:400], "sources": sources}

    # 抓取前N个页面补充信息
    page_summaries = []
    if sources:
        def _fetch_one(idx, title, url):
            content = fetch_page(url, index=idx)
            if content:
                summary = _extract_key_sentences(content, max_sentences=2, min_len=10)
                return idx, summary
            return idx, ""

        with ThreadPoolExecutor(max_workers=min(len(sources), 3)) as ex:
            futures = {ex.submit(_fetch_one, i, t, u): i for i, (t, u) in enumerate(sources)}
            for f in as_completed(futures, timeout=12):
                try:
                    _, summary = f.result()
                    if summary and summary not in page_summaries:
                        page_summaries.append(summary)
                except (FutureTimeout, Exception):
                    pass

    # 组合最终回答
    parts = [quick_answer] if quick_answer else []
    if page_summaries:
        parts.append("。".join(page_summaries[:2]))
    elif not parts:
        parts = [f"搜索「{query}」未找到详细介绍"]

    answer = "。".join(p for p in parts if p)
    return {"answer": answer[:380], "sources": sources}


if __name__ == "__main__":
    import sys
    tests = sys.argv[1:] if len(sys.argv) > 1 else ["今天北京天气", "Python asyncio用法"]
    for q in tests:
        r = smart_search(q)
        print(f"\nQ: {q}")
        print(f"A: {r['answer'][:200]}")
        print(f"   来源: {len(r['sources'])} 条")
