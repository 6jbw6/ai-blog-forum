"""内容审核：命中敏感词只做「拦下 + 记日志 + 进待审列表」，不再自动封号

词库只有几十个硬编码词，加个空格、换同音字、拆词就能绕过，对真正的垃圾信息发布者
几乎没有拦截力；反过来，讲反诈、反洗钱、数据投毒、安全攻防的技术文章很容易误伤。
旧策略是「一次子串命中 = 账号立即永久封禁且无申诉通道」，惩罚与触发条件完全不成比例。

因此分工改成：机器只负责把可疑内容挡在公开视野之外并留下审计痕迹，
**要不要封号由管理员判断**（用户管理页本就有手动封禁 / 解封）。
管理员本人豁免内容闸门——他就是审核者，否则自己的发言会卡在自己的待审队列里。
"""
import logging
from datetime import datetime
from typing import Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger("app.moderation")

# 敏感词表：命中即拦下内容并转人工审核（不是定罪依据，只是分流信号）
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


def moderate_text(text: str) -> Tuple[bool, str]:
    """检测文本是否命中敏感词。

    返回 (是否命中, 面向用户的说明)。命中多个词时列出全部。
    """
    if not text:
        return False, ""
    hits = sorted({kw for kw in BANNED_KEYWORDS if kw in text})
    if hits:
        return True, f"疑似命中违规词（{'、'.join(hits)}）"
    return False, ""


def check_content(user: User, text: str, scene: str) -> Tuple[bool, str]:
    """发布 / 编辑前的内容闸门。返回 (是否应当拦下, 说明文案)。

    命中一律写审计日志（谁、什么场景、命中哪些词），管理员场景放行但同样留痕。
    """
    violated, reason = moderate_text(text)
    if not violated:
        return False, ""

    logger.warning(
        "内容审核命中｜场景=%s｜用户=%s(id=%s)｜%s",
        scene, user.username, user.id, reason,
    )
    if user.role == "admin":
        return False, ""
    return True, reason


def violated_content_filter(column):
    """把敏感词表翻译成等价的 SQL 条件，供列表查询下推过滤。

    与 `moderate_text` 是同一份词库的两种执行位置：单条内容判定用 Python，
    分页列表用 SQL——否则必须把全表正文捞进内存才能筛出违规行。
    词库按运营需要持续扩充，因此这里同样转义 LIKE 通配符，
    避免以后加进一个含 `%` / `_` 的词时匹配范围被悄悄放大。
    """
    escaped = [
        kw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        for kw in sorted(BANNED_KEYWORDS)
    ]
    return or_(*[column.like(f"%{kw}%", escape="\\") for kw in escaped])


def ban_user(db: Session, user: User, reason: str) -> None:
    """封禁账号：立即失效（登录与既有 token 均被 is_active 校验拦截）

    只由管理员在后台手动触发，内容审核命中不再走这条路。
    """
    user.is_active = False
    user.ban_reason = reason[:255]
    user.banned_at = datetime.utcnow()
    db.commit()


def unban_user(db: Session, user: User) -> None:
    user.is_active = True
    user.ban_reason = None
    user.banned_at = None
    db.commit()
