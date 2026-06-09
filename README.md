# AI 薅羊毛日报

这个仓库会每天自动搜索 AI 圈最新的免费额度、优惠码、试用额度、API credits、创业 credits 等线索，过滤低相关结果，去重后发送邮件。

运行方式是 GitHub Actions 云端定时任务，不需要打开电脑。

## 现在能做什么

- 每天北京时间 08:00 自动运行。
- 支持在 GitHub Actions 页面手动运行。
- 从 Bing RSS、Hacker News、Reddit 等公开来源搜索线索。
- 提取具体标题、链接、来源、摘要、命中原因和可信度提示。
- 使用 `data/sent_items.json` 保存已发送记录，避免每天重复发同一条。
- 邮件发送失败或配置缺失时，在 Actions 日志里给出明确错误。
- 没有新增内容时，默认也会发送一封“今日无新增”的日报，证明任务正常运行。

## 必须填写的 GitHub Secrets

进入仓库：

`Settings → Secrets and variables → Actions → Repository secrets → New repository secret`

添加下面 5 个值：

| Secret 名称 | 填什么 |
| --- | --- |
| `EMAIL_SENDER` | 发件邮箱。建议使用 QQ 邮箱 |
| `EMAIL_PASSWORD` | 邮箱 SMTP 授权码，不是登录密码 |
| `EMAIL_RECIPIENT` | 收件邮箱。你的目标邮箱填 `565867096@qq.com` |
| `SMTP_SERVER` | QQ 邮箱填 `smtp.qq.com` |
| `SMTP_PORT` | QQ 邮箱填 `465` |

QQ 邮箱授权码位置：

`QQ邮箱 → 设置 → 账号 → POP3/IMAP/SMTP 服务 → 开启 SMTP → 生成授权码`

## 当前默认参数

这些参数已经写在脚本里，不需要你额外填写。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `LOOKBACK_HOURS` | `36` | 每次搜索最近多少小时内的线索 |
| `MAX_ITEMS` | `12` | 每封邮件最多发送多少条 |
| `SEND_EMPTY_DIGEST` | `true` | 没有新增线索时是否仍发送邮件 |

## 手动测试

进入：

`Actions → AI 薅羊毛日报 → Run workflow`

如果配置正确，几分钟内会收到测试邮件。第一次运行后，仓库里的 `data/sent_items.json` 会被自动更新，用来保存去重记录。

## 注意

这个项目抓取的是公开网页、搜索结果和社区讨论。邮件里的内容是“线索”，不是最终确认结果。领取前仍然需要打开链接确认官网规则、地区限制、过期时间和是否需要绑卡。
