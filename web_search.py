"""
联网搜索模块 — DDGS API + 智能摘要 + 网页抓取
"""
import re, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from ddgs import DDGS

TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def search_web(query, num=5):
    """DDGS 搜索，返回 [(title, url, snippet), ...]"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num, region="cn-zh"))
            items = []
            for r in results:
                title = r.get("title", "")
                url = r.get("href", "")
                body = r.get("body", "")
                items.append((title, url, body))
            return items
    except Exception as e:
        print(f"[搜索] DDGS 失败: {e}")
        return []

def fetch_page(url):
    """抓取网页正文"""
    try:
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:3000]
    except:
        return ""

def summarize(text, max_len=150):
    """简单摘要"""
    if len(text) <= max_len: return text
    sentences = re.split(r"[。！？\n]", text)
    result = []
    cur = 0
    for s in sentences:
        s = s.strip()
        if not s: continue
        if cur + len(s) > max_len: break
        result.append(s)
        cur += len(s)
    return "。".join(result) + "。"

def smart_search(query, max_results=3):
    """一步到位：搜索 → 抓取 → 归纳 → 返回摘要"""
    print(f"[搜索] {query}")
    items = search_web(query, num=max_results+2)

    if not items:
        return {"answer": f"搜索「{query}」没有结果", "sources": []}

    # 搜索摘要快速回答
    snippets = [snip for _, _, snip in items if snip]
    if snippets:
        combined = "；".join(snippets[:3])
        quick = summarize(combined, 200)
    else:
        quick = ""

    # 并行抓取前 N 个页面
    urls = [(title, url) for title, url, _ in items[:max_results] if url.startswith("http")]

    def _fetch_and_summarize(idx, title, url):
        content = fetch_page(url)
        if content:
            summary = summarize(content, 200)
            return idx, title, url, summary
        return idx, title, url, ""

    page_summaries = []
    if urls:
        with ThreadPoolExecutor(max_workers=min(len(urls), 3)) as ex:
            futures = {ex.submit(_fetch_and_summarize, i, t, u): i for i, (t, u) in enumerate(urls)}
            for f in as_completed(futures, timeout=15):
                try:
                    idx, title, url, s = f.result()
                    if s: page_summaries.append((title, url, s))
                except: pass

    parts = []
    if quick: parts.append(quick)
    if page_summaries:
        details = "。".join([s for _, _, s in page_summaries[:2]])
        if details: parts.append(details)

    answer = "。".join(parts) if parts else quick or f"搜索「{query}」未找到详细介绍"
    return {
        "answer": answer[:400],
        "sources": [(t, u) for t, u, _ in items[:max_results] if u.startswith("http")]
    }

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "今天天气"
    r = smart_search(q)
    print(f"\n回答: {r['answer']}")
    print(f"\n来源:")
    for t, u in r.get("sources", []):
        print(f"  - {t}: {u}")
