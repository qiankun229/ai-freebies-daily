# AI 薅羊毛日报

每日自动搜索 AI 领域免费额度、优惠活动并发送到邮箱 565867096@qq.com。

## 设置 Secrets（必须）
1. 打开 https://github.com/qiankun229/ai-freebies-daily/settings/secrets/actions
2. 添加以下 Repository secrets：
   - `EMAIL_SENDER`：你的发件 QQ 邮箱，例如 `565867096@qq.com`
   - `EMAIL_PASSWORD`：QQ 邮箱的 **SMTP 授权码**（不是登录密码！在 QQ 邮箱设置 → 账户 → POP3/IMAP/SMTP → 生成授权码）
   - `EMAIL_RECIPIENT`：`565867096@qq.com`
   - `SMTP_SERVER`：`smtp.qq.com`
   - `SMTP_PORT`：`465`

## 测试
点击 Actions → AI 薅羊毛日报 → Run workflow 手动测试。

成功后每天北京时间早上 8 点自动发送！

仓库：https://github.com/qiankun229/ai-freebies-daily