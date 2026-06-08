import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

# ==================== 配置通过 GitHub Secrets 传入 ====================
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.163.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

KEYWORDS = ["AI 薅羊毛", "AI free credits", "AI API 免费额度", "Claude Grok GPT DeepSeek 免费", "AgentRouter", "Cursor 优惠", "AI 免费模型", "AI 免费额度"]

def search_ai_freebies():
    results = []
    for kw in KEYWORDS:
        try:
            url = f"https://www.bing.com/search?q={requests.utils.quote(kw)}+after:{datetime.now().strftime('%Y-%m-%d')}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                results.append(f"🔍 {kw}：找到最新结果（详见 Bing 搜索）")
        except:
            results.append(f"🔍 {kw}：搜索失败")
    return results

def send_email(content):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = f"AI 薅羊毛日报 - {datetime.now().strftime('%Y-%m-%d')}"

    body = f"""
    <h2>今日 AI 领域薅羊毛资讯</h2>
    <p>更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <ul>
    {''.join([f'<li>{item}</li>' for item in content]) if content else '<li>今日暂无新羊毛</li>'}
    </ul>
    <p><small>自动发送 | GitHub Actions</small></p>
    """
    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
    server.quit()

if __name__ == "__main__":
    freebies = search_ai_freebies()
    send_email(freebies)
    print("邮件发送完成")