import random
import re
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.search_log import SearchLog
from app.models.article import Article

FALLBACK_PROMPTS = [
    "Transformer 自注意力为什么要除以 $\\sqrt{d_k}$？",
    "多路召回 (Hybrid Search) 相比单一向量检索有什么优势？",
    "显存不够时如何基于 LoRA / QLoRA 微调大语言模型？",
    "LoRA 微调权重合并后为什么在推理阶段零延迟？",
    "自注意力机制中的 Q、K、V 矩阵是如何计算和投影的？",
    "如何基于 LangChain 实现标题感知与重叠窗口的递归文本分块？",
    "BM25 关键词匹配与向量余弦相似度各自擅长解决什么检索问题？",
    "企业级 RAG 系统如何设计多阶段召回与交叉重排 (Rerank) 流水线？"
]

# 闲聊/身份类问句黑名单：这类问句与论坛技术内容无关，禁止进入热度统计与推荐池
_CHITCHAT_RE = re.compile(
    r"你是谁|你叫什么|自我介绍|介绍.{0,4}自己|你是做|你是什么|你好|您好"
    r"|谢谢|感谢|多谢|再见|拜拜|在吗|在么|你是机器人|你是人还是",
    re.IGNORECASE
)


def is_chitchat_query(query: str) -> bool:
    """判定是否为与知识库无关的闲聊/身份类问句（如「你是谁」「你好」）"""
    if not query:
        return True
    t = query.strip().lower()
    if not t:
        return True
    return bool(_CHITCHAT_RE.search(t)) or t in {"hi", "hello", "hey"}


def record_search_query(db: Session, query: str, search_type: str = "ai_ask") -> None:
    """
    记录或累加用户搜索与 AI 提问热度
    
    :param db: 数据库会话
    :param query: 检索或提问文本
    :param search_type: 提问来源 (ai_ask | semantic_search | portal_search)
    """
    if not query:
        return
    q = query.strip()
    if len(q) < 2 or len(q) > 200:
        return
    # 闲聊/身份类问句不进入热度统计，避免污染热搜概念与推荐问题池
    if is_chitchat_query(q):
        return
    try:
        log = db.query(SearchLog).filter(SearchLog.query == q).first()
        if log:
            log.hit_count += 1
            log.last_searched_at = datetime.utcnow()
            log.search_type = search_type
        else:
            log = SearchLog(
                query=q,
                search_type=search_type,
                hit_count=1,
                last_searched_at=datetime.utcnow()
            )
            db.add(log)
        db.commit()
    except Exception:
        db.rollback()


def get_dynamic_recommended_questions(db: Session, limit: int = 8, shuffle: bool = True) -> List[str]:
    """
    结合用户历史搜索热度 (SearchLog)、高浏览技术博文 (Article) 与核心知识库题库，
    多维融合动态生成智能推荐问题清单。
    
    推荐生成策略:
    1. 搜索与提问频次最高的热词 / 真实问题 (Top Search Heat)
    2. 热度博文衍生出的深度阅读与原理剖析问题 (Top Articles)
    3. 核心知识库高质量兜底题库 (Core Technical Fallback)
    4. 动态采样与打乱，支持用户点击「换一批」探索新问题
    """
    candidate_questions: List[str] = []
    seen = set()

    def add_question(q: str):
        q_clean = q.strip()
        if q_clean and q_clean not in seen and len(q_clean) >= 4:
            seen.add(q_clean)
            candidate_questions.append(q_clean)

    # 1. 召回最高热度的搜索记录 (按 hit_count 降序，其次按更新时间降序)
    try:
        hot_logs = (
            db.query(SearchLog)
            .order_by(desc(SearchLog.hit_count), desc(SearchLog.last_searched_at))
            .limit(16)
            .all()
        )
        for item in hot_logs:
            text = item.query.strip()
            # 过滤闲聊/身份类问句，避免「你是谁」类内容混入推荐问题
            if is_chitchat_query(text):
                continue
            # 如果结尾未包含标点符号，智能补充为问句提升自然交互感
            if not any(text.endswith(p) for p in ["?", "？", "!", "！", "。"]):
                if any(w in text for w in ["什么", "怎么", "如何", "为什么", "原理", "机制", "区别", "优化", "实战"]):
                    text = f"{text}？"
                else:
                    text = f"请详细解析一下 {text} 的实现原理？"
            add_question(text)
    except Exception:
        pass

    # 2. 结合浏览量最高的已发布博文动态生成技术剖析提问
    try:
        top_articles = (
            db.query(Article)
            .filter(Article.is_published == True)
            .order_by(desc(Article.views_count), desc(Article.created_at))
            .limit(6)
            .all()
        )
        for art in top_articles:
            title = art.title.strip()
            # 提炼博文核心问法
            add_question(f"请总结《{title}》的核心要点？")
            add_question(f"在《{title}》中提到了哪些关键实现细节？")
    except Exception:
        pass

    # 3. 补充底层技术知识库精选兜底题
    for prompt in FALLBACK_PROMPTS:
        add_question(prompt)

    # 4. 打乱与采样策略：保留前 2 个最高热度问题，对其余候选池进行洗牌，保障既有热度又有新鲜感
    if shuffle and len(candidate_questions) > limit:
        top_priority = candidate_questions[:2]
        remaining = candidate_questions[2:]
        random.shuffle(remaining)
        selected = top_priority + remaining[: limit - len(top_priority)]
        return selected[:limit]

    return candidate_questions[:limit]


FALLBACK_HOT_KEYWORDS = [
    "AI Agent 认知架构",
    "LangGraph 循环流控",
    "Multi-Agent 多智能体协同",
    "LoRA 显存优化",
    "自注意力机制缩放",
    "多路召回与混合检索",
    "Function Calling 实战",
    "Self-RAG 反思纠错"
]


def get_dynamic_hot_keywords(db: Session, limit: int = 6) -> List[str]:
    """
    根据用户实际搜索日志 (SearchLog) 热度排名、热门博文分类/标签及高频技术概念，
    动态生成热搜概念关键词清单。
    """
    keywords: List[str] = []
    seen = set()

    def add_kw(kw: str):
        k = kw.strip().rstrip("?？!！。")
        if k and k not in seen and 2 <= len(k) <= 30:
            seen.add(k)
            keywords.append(k)

    # 1. 召回最高热度的实际搜索记录
    try:
        hot_logs = (
            db.query(SearchLog)
            .order_by(desc(SearchLog.hit_count), desc(SearchLog.last_searched_at))
            .limit(10)
            .all()
        )
        for log in hot_logs:
            # 过滤闲聊/身份类问句，热搜概念只保留技术检索词
            if is_chitchat_query(log.query):
                continue
            add_kw(log.query)
    except Exception:
        pass

    # 2. 从浏览量高的博文标题或标签提炼核心概念
    try:
        top_articles = (
            db.query(Article)
            .filter(Article.is_published == True)
            .order_by(desc(Article.views_count), desc(Article.likes_count))
            .limit(6)
            .all()
        )
        for art in top_articles:
            if art.tags:
                for t in art.tags:
                    add_kw(t.name)
            title = art.title
            if "：" in title:
                add_kw(title.split("：")[0])
            elif ":" in title:
                add_kw(title.split(":")[0])
    except Exception:
        pass

    # 3. 兜底精选高频硬核概念
    for kw in FALLBACK_HOT_KEYWORDS:
        add_kw(kw)

    return keywords[:limit]

