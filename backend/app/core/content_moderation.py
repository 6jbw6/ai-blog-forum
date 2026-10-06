"""内容违规实时监测与自动封禁

发布博文 / 评论时对文本做敏感词检测，命中即自动封禁发布者账号。
词库为基础示例，可按运营需要持续扩充。
"""
from datetime import datetime
from typing import Tuple

from sqlalchemy.orm import Session

from app.models.user import User

# 敏感词表：命中即判定为严重违规并自动封号
BANNED_KEYWORDS = {
    # 违禁与犯罪
    "毒品", "冰毒", "摇头丸", "枪支买卖", "弹药贩卖", "办假证", "代开发票",
    # 赌博
    "赌博", "赌场", "博彩网站", "网赌", "六合彩",
    # 色情与招嫖
    "嫖娼", "卖淫", "援交", "约炮", "裸聊",
    # 诈骗与黑产
    "刷单兼职", "洗钱", "诈骗教程", "钓鱼网站制作", "木马病毒传播",
    # 暴恐与极端
    "恐怖袭击", "爆炸物制作", "自杀攻略",
    # 辱骂与人身攻击
    "傻逼", "煞笔", "他妈的滚", "去死吧", "全家死光",
}

# 账号封禁时对外展示的统一前缀
AUTO_BAN_SOURCE = "系统自动封禁"


def moderate_text(text: str) -> Tuple[bool, str]:
    """检测文本是否命中敏感词。

    返回 (是否违规, 命中原因)。命中多个词时列出全部。
    """
    if not text:
        return False, ""
    hits = sorted({kw for kw in BANNED_KEYWORDS if kw in text})
    if hits:
        return True, f"内容包含违规词：{'、'.join(hits)}"
    return False, ""


def ban_user(db: Session, user: User, reason: str) -> None:
    """封禁账号：立即失效（登录与既有 token 均被 is_active 校验拦截）"""
    user.is_active = False
    user.ban_reason = reason[:255]
    user.banned_at = datetime.utcnow()
    db.commit()


def unban_user(db: Session, user: User) -> None:
    user.is_active = True
    user.ban_reason = None
    user.banned_at = None
    db.commit()


def auto_ban_if_violation(db: Session, user: User, text: str) -> bool:
    """发布内容前调用：命中敏感词则自动封号并返回 True（调用方应中断发布并提示）"""
    violated, reason = moderate_text(text)
    if violated and user.role != "admin":
        ban_user(db, user, f"{AUTO_BAN_SOURCE}：{reason}")
        return True
    return False
