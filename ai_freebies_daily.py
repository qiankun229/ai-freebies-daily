import hashlib
import html
import json
import os
import re
import smtplib
import subprocess
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import xml.etree.ElementTree as ET

import requests
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")
DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "sent_items.json")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "").strip()
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "465") or "465")

LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "36") or "36")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "12") or "12")
SEND_EMPTY_DIGEST = (os.getenv("SEND_EMPTY_DIGEST", "true") or "true").lower() in {"1", "true", "yes", "y"}

SEARCH_QUERIES = [
    "AI free credits",
    "\"free API credits\" AI",
    "\"AI API\" \"free credits\"",
    "\"free tier\" \"AI API\"",
    "\"startup credits\" AI",
    "\"Claude\" \"free credits\"",
    "\"OpenAI\" \"free credits\"",
    "\"Gemini\" \"free credits\"",
    "\"Cursor\" coupon",
    "\"Windsurf\" coupon",
    "\"Grok\" \"free credits\"",
    "\"DeepSeek\" \"free API\"",
    "\"OpenRouter\" credits",
    "\"Groq\" \"free credits\"",
    "\"Mistral\" \"free credits\"",
    "\"Perplexity\" coupon",
    "\"Replit\" \"free credits\"",
    "AI tool lifetime deal",
    "AI 免费额度",
    "AI API 免费额度",
    "AI 工具 优惠码",
    "AI 赠送 credits",
    "Claude 免费额度",
    "Cursor 优惠码",
    "OpenAI 免费 credits",
    "Gemini API 免费额度",
]

REDDIT_SUBS = ["LocalLLaMA", "OpenAI", "ChatGPT", "ClaudeAI", "SaaS"]

TRUSTED_DOMAINS = {
    "openai.com", "anthropic.com", "ai.google.dev", "cloud.google.com",
    "developers.googleblog.com", "x.ai", "deepseek.com", "cursor.com",
    "windsurf.com", "codeium.com", "replit.com", "vercel.com", "mistral.ai",
    "perplexity.ai", "groq.com", "openrouter.ai", "together.ai",
    "huggingface.co", "github.com", "microsoft.com", "azure.microsoft.com",
    "aws.amazon.com", "producthunt.com", "news.ycombinator.com"
}

POSITIVE = [
    (r"\bfree\s+api\s+credits?\b", 7, "free API credits"),
    (r"\bfree\s+credits?\b", 6, "free credits"),
    (r"\bapi\s+credits?\b", 4, "API credits"),
    (r"\bstartup\s+credits?\b", 5, "startup credits"),
    (r"\bfree\s+tier\b", 4, "free tier"),
    (r"\bfree\s+trial\b", 3, "free trial"),
    (r"\bcoupon\b|\bpromo\s*code\b|\bdiscount\b", 4, "coupon / discount"),
    (r"\blifetime\s+deal\b", 3, "lifetime deal"),
    (r"\bcredits?\b", 2, "credits"),
    (r"免费额度|免费\s*API|赠送\s*额度|注册送|优惠码|折扣|限时免费|羊毛", 6, "中文免费/优惠信号"),
]

ENTITIES = [
    (r"\bopenai\b|\bchatgpt\b", 2, "OpenAI / ChatGPT"),
    (r"\banthropic\b|\bclaude\b", 2, "Anthropic / Claude"),
    (r"\bgemini\b|\bgoogle\s+ai\b|\bvertex\s+ai\b", 2, "Google Gemini"),
    (r"\bgrok\b|\bxai\b|\bx\.ai\b", 2, "Grok / xAI"),
    (r"\bdeepseek\b", 2, "DeepSeek"),
    (r"\bcursor\b", 2, "Cursor"),
    (r"\bwindsurf\b|\bcodeium\b", 2, "Windsurf / Codeium"),
    (r"\breplit\b", 2, "Replit"),
    (r"\bmistral\b", 2, "Mistral"),
    (r"\bperplexity\b", 2, "Perplexity"),
    (r"\bgroq\b", 2, "Groq"),
    (r"\bopenrouter\b", 2, "OpenRouter"),
    (r"\bhugging\s*face\b|\bhuggingface\b", 2, "Hugging Face"),
    (r"\bai\b|\bllm\b|\bagent\b|\bmcp\b", 1, "AI / LLM"),
]

NEGATIVE = [
    (r"\bcrack(ed)?\b|破解版|破解|盗版|torrent|keygen", -9, "疑似破解/盗版"),
    (r"\bjob\b|\bhiring\b|招聘|求职", -4, "招聘噪音"),
    (r"\bcourse\b|\btutorial\b|教程|培训|训练营", -4, "教程噪音"),
    (r"\bbest\s+free\s+ai\s+tools\b|免费AI工具大全|工具合集", -3, "泛工具合集"),
    (r"\bwallpaper\b|壁纸|头像", -5, "无关内容"),
    (r"\bcasino\b|\bcrypto\b|\bairdrop\b|博彩|成人", -6, "低质营销噪音"),
]


def now():
    return datetime.now(TZ)


def clean(text):
    text = text or ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_time(value):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(TZ)
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ)
    except Exception:
        return None


def normalize_url(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    kept = []
    for key, values in query.items():
        low = key.lower()
        if low.startswith("utm_") or low in {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "spm"}:
            continue
        for value in values:
            kept.append((key, value))
    path = re.sub(r"/+$", "", parsed.path)
    return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), path, "", urlencode(kept, doseq=True), ""))


def domain(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def title_key(title):
    value = clean(title).lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)
    return value[:120]


def item_hash(item):
    return digest(normalize_url(item["url"]) or title_key(item["title"]))


def session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "ai-freebies-daily/1.0",
        "Accept": "application/json,text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def bing_rss(s, query, since):
    items, errors = [], []
    q = f"{query} after:{since.date().isoformat()}"
    url = "https://www.bing.com/search?" + urlencode({"q": q, "format": "rss", "count": "10", "setlang": "zh-Hans"})
    try:
        r = s.get(url, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        for node in root.findall(".//item"):
            title = clean(node.findtext("title"))
            link = clean(node.findtext("link"))
            desc = clean(node.findtext("description"))
            pub = parse_time(node.findtext("pubDate"))
            if title and link:
                items.append({
                    "title": title,
                    "url": normalize_url(link),
                    "source": "Bing RSS",
                    "summary": desc,
                    "query": query,
                    "published_at": pub.isoformat() if pub else "",
                })
    except Exception as e:
        errors.append(f"Bing RSS 失败：{query}｜{type(e).__name__}: {e}")
    return items, errors


def hacker_news(s, query, since):
    items, errors = [], []
    ts = int(since.astimezone(timezone.utc).timestamp())
    url = "https://hn.algolia.com/api/v1/search_by_date?" + urlencode({
        "query": query,
        "tags": "story",
        "hitsPerPage": "15",
        "numericFilters": f"created_at_i>{ts}",
    })
    try:
        r = s.get(url, timeout=20)
        r.raise_for_status()
        for hit in r.json().get("hits", []):
            title = clean(hit.get("title") or hit.get("story_title"))
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            created = parse_time(hit.get("created_at"))
            if title and link:
                items.append({
                    "title": title,
                    "url": normalize_url(link),
                    "source": "Hacker News",
                    "summary": clean(hit.get("story_text") or ""),
                    "query": query,
                    "published_at": created.isoformat() if created else "",
                })
    except Exception as e:
        errors.append(f"Hacker News 失败：{query}｜{type(e).__name__}: {e}")
    return items, errors


def reddit(s, query, since):
    items, errors = [], []
    for sub in REDDIT_SUBS:
        url = f"https://www.reddit.com/r/{sub}/search.json?" + urlencode({
            "q": query,
            "restrict_sr": "1",
            "sort": "new",
            "t": "week",
            "limit": "8",
        })
        try:
            r = s.get(url, timeout=20, headers={"User-Agent": "ai-freebies-daily/1.0"})
            if r.status_code in {403, 429}:
                errors.append(f"Reddit 访问受限：r/{sub}｜HTTP {r.status_code}")
                continue
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                p = child.get("data", {})
                created = datetime.fromtimestamp(p.get("created_utc", 0), timezone.utc).astimezone(TZ)
                if created < since:
                    continue
                title = clean(p.get("title"))
                link = p.get("url") or f"https://www.reddit.com{p.get('permalink', '')}"
                if title and link:
                    items.append({
                        "title": title,
                        "url": normalize_url(link),
                        "source": f"Reddit r/{sub}",
                        "summary": clean(p.get("selftext") or ""),
                        "query": query,
                        "published_at": created.isoformat(),
                    })
            time.sleep(0.3)
        except Exception as e:
            errors.append(f"Reddit 失败：r/{sub}｜{query}｜{type(e).__name__}: {e}")
    return items, errors


def score(item):
    text = f"{item['title']} {item.get('summary', '')} {item['url']}".lower()
    item["score"] = 0
    item["reasons"] = []
    for rules in (POSITIVE, ENTITIES, NEGATIVE):
        for pattern, points, reason in rules:
            if re.search(pattern, text, re.I):
                item["score"] += points
                item["reasons"].append(reason)
    pub = parse_time(item.get("published_at"))
    if pub and pub >= now() - timedelta(hours=48):
        item["score"] += 2
        item["reasons"].append("48小时内")
    d = domain(item["url"])
    item["domain"] = d
    if d in TRUSTED_DOMAINS:
        item["score"] += 3
        item["reasons"].append("官方/高可信域名")
    elif item["source"].startswith(("Hacker News", "Reddit")):
        item["score"] += 1
        item["reasons"].append("社区新帖")
    if item["source"] == "Bing RSS":
        item["reasons"].append("搜索引擎结果，需二次确认")
    item["reasons"] = list(dict.fromkeys(item["reasons"]))
    if d in TRUSTED_DOMAINS and item["score"] >= 8:
        item["confidence"] = "较可信"
    elif item["score"] >= 7:
        item["confidence"] = "可关注"
    else:
        item["confidence"] = "需人工确认"
    item["hash"] = item_hash(item)
    return item


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {"version": 1, "items": []}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("items"), list):
            return data
    except Exception:
        pass
    return {"version": 1, "items": []}


def save_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")


def known_hashes(history):
    return {x.get("hash") for x in history.get("items", []) if x.get("hash")}


def prune_history(history):
    cutoff = now() - timedelta(days=180)
    kept = []
    for x in history.get("items", []):
        t = parse_time(x.get("sent_at"))
        if not t or t >= cutoff:
            kept.append(x)
    history["items"] = kept
    return history


def dedupe(items):
    seen_hash, seen_title, out = set(), set(), []
    for item in items:
        h = item.get("hash") or item_hash(item)
        tk = title_key(item["title"])
        if h in seen_hash or tk in seen_title:
            continue
        seen_hash.add(h)
        seen_title.add(tk)
        out.append(item)
    return out


def collect():
    s = session()
    since = now() - timedelta(hours=LOOKBACK_HOURS)
    all_items, errors = [], []
    reddit_queries = {"AI free credits", "\"AI API\" \"free credits\"", "\"Claude\" \"free credits\"", "\"Cursor\" coupon", "AI 免费额度"}
    for q in SEARCH_QUERIES:
        for func in (bing_rss, hacker_news):
            items, err = func(s, q, since)
            all_items.extend(items)
            errors.extend(err)
        if q in reddit_queries:
            items, err = reddit(s, q, since)
            all_items.extend(items)
            errors.extend(err)
        time.sleep(0.2)
    return [score(x) for x in all_items], errors


def check_email_config():
    missing = [k for k, v in {
        "EMAIL_SENDER": EMAIL_SENDER,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
        "EMAIL_RECIPIENT": EMAIL_RECIPIENT,
    }.items() if not v]
    if missing:
        raise RuntimeError("缺少 GitHub Actions Secrets：" + ", ".join(missing))


def short(text, limit=220):
    text = clean(text)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def fmt_time(value):
    t = parse_time(value)
    return t.strftime("%Y-%m-%d %H:%M") if t else "未知时间"


def build_html(items, raw_count, filtered_count, errors):
    date = now().strftime("%Y-%m-%d %H:%M")
    if items:
        body_items = []
        for i, item in enumerate(items, 1):
            body_items.append(f"""
            <li style="margin:0 0 16px 0;">
              <div><strong>{i}. <a href="{html.escape(item['url'])}" target="_blank">{html.escape(item['title'])}</a></strong></div>
              <div style="font-size:13px;color:#666;margin-top:4px;">
                来源：{html.escape(item['source'])}｜域名：{html.escape(item.get('domain',''))}｜时间：{html.escape(fmt_time(item.get('published_at')))}｜评分：{item['score']}｜可信度：{html.escape(item['confidence'])}
              </div>
              <div style="font-size:13px;color:#666;margin-top:4px;">
                命中原因：{html.escape('、'.join(item.get('reasons', [])))}｜搜索词：{html.escape(item.get('query',''))}
              </div>
              <p style="margin:6px 0 0;color:#444;">{html.escape(short(item.get('summary','')))}</p>
            </li>
            """)
        items_html = "\n".join(body_items)
        headline = f"本次发现 {len(items)} 条未发送过的 AI 免费额度/优惠线索。"
    else:
        items_html = "<li>今天没有筛出新的高相关线索。系统仍然完成了搜索、过滤和去重。</li>"
        headline = "本次没有发现新的高相关线索。"

    err_html = ""
    if errors:
        err_html = "<h3>运行提示</h3><ul>" + "".join(f"<li>{html.escape(e)}</li>" for e in errors[:12]) + "</ul>"

    return f"""
    <html>
      <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,'Microsoft YaHei',sans-serif;line-height:1.6;color:#222;">
        <h2>AI 薅羊毛日报</h2>
        <p>更新时间：{html.escape(date)}（北京时间）</p>
        <p><strong>{html.escape(headline)}</strong></p>
        <p style="color:#666;font-size:13px;">搜索范围：最近 {LOOKBACK_HOURS} 小时。原始候选：{raw_count} 条；过滤去重后：{filtered_count} 条；本邮件最多发送：{MAX_ITEMS} 条。</p>
        <ol style="padding-left:20px;">{items_html}</ol>
        {err_html}
        <hr>
        <p style="font-size:12px;color:#777;">自动发送｜GitHub Actions｜已启用链接级与标题级去重。邮件内容是线索，领取前仍需确认官网规则、地区限制、过期时间和是否需要绑卡。</p>
      </body>
    </html>
    """


def send_email(subject, body):
    check_email_config()
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())


def persist_history_with_git():
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=False)
        status = subprocess.run(["git", "status", "--porcelain", HISTORY_FILE], capture_output=True, text=True, check=False)
        if not status.stdout.strip():
            print("去重历史无变化，不提交。")
            return
        subprocess.run(["git", "add", HISTORY_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update sent items history"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("去重历史已提交回仓库。")
    except Exception as e:
        print(f"去重历史提交失败，不影响邮件发送：{type(e).__name__}: {e}")


def main():
    history = prune_history(load_history())
    sent = known_hashes(history)
    items, errors = collect()
    raw_count = len(items)

    filtered = []
    for item in items:
        reasons = item.get("reasons", [])
        if item["score"] < 5:
            continue
        if item["hash"] in sent:
            continue
        if "疑似破解/盗版" in reasons or "无关内容" in reasons:
            continue
        filtered.append(item)

    unique = dedupe(filtered)
    unique.sort(key=lambda x: (x["score"], parse_time(x.get("published_at")) or datetime.min.replace(tzinfo=TZ)), reverse=True)
    selected = unique[:MAX_ITEMS]

    subject = f"AI 薅羊毛日报 - {now().strftime('%Y-%m-%d')} - 新增 {len(selected)} 条"
    body = build_html(selected, raw_count, len(unique), errors)

    if selected or SEND_EMPTY_DIGEST:
        send_email(subject, body)
        print(f"邮件发送完成：{len(selected)} 条新增线索。")
    else:
        print("没有新增线索，且 SEND_EMPTY_DIGEST=false，本次不发送邮件。")

    if selected:
        for item in selected:
            history.setdefault("items", []).append({
                "hash": item["hash"],
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "domain": item.get("domain", ""),
                "score": item["score"],
                "confidence": item["confidence"],
                "sent_at": now().isoformat(),
            })
    save_history(prune_history(history))
    persist_history_with_git()


if __name__ == "__main__":
    main()
