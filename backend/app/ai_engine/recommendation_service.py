import random
import re
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.search_log import SearchLog
from app.models.article import Article
from app.ai_engine.embedding import get_sparse_embedding, analyze_query_informativeness
from app.ai_engine.retrieval_index import retrieval_index, IndexSnapshot
from app.core.config import settings

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


def _get_kb_snapshot(db: Session) -> Optional[IndexSnapshot]:
    """
    获取进程内检索索引快照，供相关性门禁做召回判定。
    快照获取失败（如向量库尚未按新格式重建）时返回 None —— 门禁对空知识库
    一律放行（fail-open），保证热度统计不会因向量库未初始化而被整体冻结。
    """
    try:
        return retrieval_index.get_snapshot(db)
    except Exception:
        return None


def _passes_kb_gate(query: str, snapshot: Optional[IndexSnapshot]) -> bool:
    """
    单条查询与知识库语料的相关性判定，两道校验依次执行：

    1. 主题词覆盖校验：按 jieba 通用词频把查询词元区分主题词与框架泛词，
       当「未登录的主题词」多于「已登录的主题词」时判定语料未覆盖该主题。
       背景：覆盖率门控只统计词表内词元，对 OOV 完全失明 —— 语料扩容后
       「红烧肉怎么做」中的泛词（怎么/做）命中词表并贡献了 0.6 的假覆盖率，
       而真正的主题词「红烧肉」是 OOV，必须靠本层拦截。
    2. 混合召回门控：完整复用检索主链路 (IndexSnapshot.search) 的召回判据，
       语义即「该查询在站内搜索时能否实际召回博文切片」：
       - 短查询靠查询覆盖率救回（如 "rag" 词法分仅 0.11 但覆盖率 1.0）；
       - 长查询靠融合分放行（如 "LoRA微调的原理是什么" 融合分 0.187 >= 0.18）。

    校验异常时放行（fail-open）：相关性门禁只做降噪，绝不阻断正常热度记录。
    """
    if snapshot is None or snapshot.size == 0:
        return True
    try:
        # 第一道：主题词覆盖校验（纯泛词查询视为无主题，同样拒绝）
        info = analyze_query_informativeness(query)
        oov_topics, known_topics = info["informative_oov"], info["informative_known"]
        if len(oov_topics) > len(known_topics):
            return False
        if not oov_topics and not known_topics:
            return False

        # 第二道：混合召回门控
        scored = snapshot.search(
            query_sparse=get_sparse_embedding(query),
            query_text=query,
            top_k=1,
            threshold=settings.RAG_SIMILARITY_THRESHOLD,
        )
        return bool(scored)
    except Exception:
        return True


def is_kb_relevant_query(db: Session, query: str) -> bool:
    """判定查询能否从知识库实际召回内容（供热度统计入库前过滤离题查询）"""
    return _passes_kb_gate(query, _get_kb_snapshot(db))


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
    # 与知识库语料无关的查询（站内搜索根本召回不到内容的词，如菜谱/股票类检索）
    # 同样不计入热度，防止热搜概念与推荐问题池被离题词污染
    if not is_kb_relevant_query(db, q):
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
    1. 搜索与提问频次最高的热词 / 真实问题 (Top Search Heat)，仅保留闲聊过滤与
       知识库相关性门禁双校验通过的技术检索词
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
        # 一次性获取检索索引快照做相关性过滤，使门禁生效前遗留的离题热度记录不再混入推荐
        kb_snapshot = _get_kb_snapshot(db)
        for item in hot_logs:
            text = item.query.strip()
            # 过滤闲聊/身份类问句，避免「你是谁」类内容混入推荐问题
            if is_chitchat_query(text):
                continue
            # 过滤无法从知识库召回内容的离题查询
            if not _passes_kb_gate(text, kb_snapshot):
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

    搜索日志只保留能实际召回知识库内容的技术检索词，闲聊与离题查询不上榜。
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
        # 一次性获取检索索引快照做相关性过滤，使门禁生效前遗留的离题热度记录不再上榜
        kb_snapshot = _get_kb_snapshot(db)
        for log in hot_logs:
            # 过滤闲聊/身份类问句，热搜概念只保留技术检索词
            if is_chitchat_query(log.query):
                continue
            # 过滤无法从知识库召回内容的离题查询（如「红烧肉怎么做」）
            if not _passes_kb_gate(log.query, kb_snapshot):
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

