"""邮箱准入策略：只接受主流邮箱服务商，不接受自有域名 / 自建邮局地址。

维护说明：域名清单是唯一事实来源，前端 `frontend/src/utils/validate.ts` 保存同一份清单，
用于输入框即时提示；后端这里是最终校验（注册与资料修改都会走）。新增服务商时两边同时加。
"""

MAINSTREAM_EMAIL_DOMAINS = frozenset({
    # 国内主流免费邮
    "qq.com", "vip.qq.com", "foxmail.com",
    "163.com", "126.com", "yeah.net", "188.com", "88.com", "163.net",
    "sina.com", "sina.cn", "vip.sina.com",
    "sohu.com", "21cn.com", "tom.com", "263.net", "aliyun.com",
    # 国内运营商邮
    "139.com", "189.cn", "wo.cn",
    # 国际主流
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "live.cn", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "yahoo.com", "yahoo.co.jp", "ymail.com", "rocketmail.com",
    "zoho.com", "zohomail.com",
    "proton.me", "protonmail.com",
    "gmx.com", "gmx.de", "gmx.net", "web.de", "mail.com",
    "yandex.com", "yandex.ru", "ya.ru",
    "aol.com", "fastmail.com", "fastmail.fm",
    "tutanota.com", "tuta.io", "hushmail.com", "hey.com",
    "naver.com", "daum.net", "hanmail.net", "nate.com",
})

# 自有域名邮箱（含腾讯企业邮 / 阿里企业邮 / 飞书 / 自建邮局）一律拒绝
EMAIL_DOMAIN_REJECT_MESSAGE = "暂不支持自有域名邮箱，请使用 QQ、163、Gmail、Outlook、iCloud 等主流邮箱"


def email_domain_of(email: str) -> str:
    return (email or "").rsplit("@", 1)[-1].strip().lower()


def is_mainstream_email(email: str) -> bool:
    """域名必须在主流服务商清单内（大小写不敏感）"""
    return email_domain_of(email) in MAINSTREAM_EMAIL_DOMAINS
