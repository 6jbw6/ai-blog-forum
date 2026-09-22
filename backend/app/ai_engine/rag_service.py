import json
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from sqlalchemy.orm import Session
from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.ai_engine.chunking import MarkdownChunker
from app.ai_engine.embedding import (
    get_sparse_embedding,
    get_sparse_embeddings,
    fit_embedding_corpus,
    sparse_vector_to_json,
)
from app.ai_engine.retrieval_index import retrieval_index
from app.ai_engine.llm_client import UnifiedLLMClient
from app.ai_engine.vector_store import strip_query_stopwords, tokenize
from app.core.config import settings

logger = logging.getLogger("app.rag")


class RAGService:
    """
    RAG (检索增强生成) 全生命周期服务体系

    架构全流程:
    1. 知识录入阶段 (Ingestion): Markdown 解析 -> 语义感知识别切块 -> TF-IDF 稀疏向量化 -> MySQL 切片持久化
    2. 检索阶段 (Retrieval): 用户 Query 向量化 -> 进程内稀疏索引快照 (CSR + BM25 缓存)
       -> 多路召回与混合加权排序 -> 提取 Top-K 知识切片
    3. 上下文合成 (Augmentation): 注入博主 Persona、防幻觉提示词与知识溯源锚点
    4. 生成阶段 (Generation): 大模型流式输出 (SSE) + 结构化引用卡片直达联动
    """

    def __init__(self):
        self.chunker = MarkdownChunker(target_chunk_size=450, chunk_overlap=60)
        self.llm = UnifiedLLMClient()

    def index_article(self, db: Session, article_id: int) -> int:
        """为单篇文章构建稀疏向量索引切片"""
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article or not article.content:
            return 0

        # 1. 标题感知递归切块
        raw_chunks = self.chunker.split_text(article.title, article.content)

        # 2. 清理旧切片
        db.query(ArticleChunk).filter(ArticleChunk.article_id == article_id).delete()

        # 3. 批量生成稀疏向量并存储（一次矩阵变换，避免逐条 transform 的重复开销）
        contents = [item["content"] for item in raw_chunks]
        embeddings = get_sparse_embeddings(contents)
        chunk_objects = []
        for idx, item in enumerate(raw_chunks):
            chunk_obj = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_title=item.get("title", article.title),
                content=item["content"],
                embedding_json=sparse_vector_to_json(embeddings[idx]),
                token_count=item.get("token_count", len(item["content"]))
            )
            chunk_objects.append(chunk_obj)

        db.add_all(chunk_objects)
        article.vector_status = "indexed"
        db.commit()
        retrieval_index.invalidate()

        logger.info(f"Article '{article.title}' (ID: {article.id}) indexed successfully with {len(chunk_objects)} chunks.")
        return len(chunk_objects)

    def reindex_all_articles(self, db: Session) -> Dict[str, int]:
        """
        全量重建所有已发布博文的向量索引

        两阶段执行：先对全量切片拟合 TF-IDF 词表/IDF（全局统计），再统一编码落库，
        避免逐篇编码时 IDF 只反映单篇内容导致权重失真。
        """
        articles = db.query(Article).filter(
            Article.is_published == True,   # noqa: E712
            Article.is_private == False     # noqa: E712
        ).all()

        # 阶段一：全局切块并拟合词表
        pending: List[tuple] = []
        all_chunk_texts: List[str] = []
        for art in articles:
            raw_chunks = self.chunker.split_text(art.title, art.content)
            pending.append((art, raw_chunks))
            all_chunk_texts.extend(item["content"] for item in raw_chunks)

        if not all_chunk_texts:
            return {"articles_indexed": 0, "total_chunks": 0}

        fit_embedding_corpus(all_chunk_texts)

        # 阶段二：统一编码并写入
        total_chunks = 0
        for art, raw_chunks in pending:
            db.query(ArticleChunk).filter(ArticleChunk.article_id == art.id).delete()
            embeddings = get_sparse_embeddings([item["content"] for item in raw_chunks])
            db.add_all([
                ArticleChunk(
                    article_id=art.id,
                    chunk_index=idx,
                    chunk_title=item.get("title", art.title),
                    content=item["content"],
                    embedding_json=sparse_vector_to_json(embeddings[idx]),
                    token_count=item.get("token_count", len(item["content"]))
                )
                for idx, item in enumerate(raw_chunks)
            ])
            art.vector_status = "indexed"
            total_chunks += len(raw_chunks)

        db.commit()
        retrieval_index.invalidate()
        logger.info(f"全量向量重构完成：{len(articles)} 篇博文 / {total_chunks} 个切片")
        return {"articles_indexed": len(articles), "total_chunks": total_chunks}

    def semantic_search(self, db: Session, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """自然语言语义检索 (突破传统关键词硬匹配)，搜索单位是文章而非切片"""
        snapshot = retrieval_index.get_snapshot(db)
        if snapshot.size == 0:
            return []

        # 多路召回与重排（扩大召回池：文章级主题过滤会淘汰「仅正文顺带提及」的文章）
        scored = snapshot.search(
            query_sparse=get_sparse_embedding(query),
            query_text=query,
            top_k=top_k * 4,
            threshold=settings.RAG_SIMILARITY_THRESHOLD
        )

        # 文章级主题判定：切片级门控对单词查询天然失明（命中即覆盖率 1.0），
        # 正文里顺带引用了查询词的文章（如 RAG 文章举例「搜“显存不够”能召回
        # “LoRA量化减小显存”」）会以单个低分切片混入结果。判据取强信号之——
        # 标题/摘要概念命中（词级包含，QLoRA 对 lora、vLLM 对 llm 也算），
        # 或多个切片命中正文，或最佳切片分够高（正文深度讨论）。
        q_tokens = set(tokenize(strip_query_stopwords(query)))

        def concept_hit(text_tokens: frozenset) -> bool:
            return any(qt in t for t in text_tokens for qt in q_tokens)

        # 按文章去重聚合（dict 保序，scored 已按分数降序），每篇保留相关度最高的一段
        seen_articles: Dict[Any, Dict[str, Any]] = {}
        for item in scored:
            info = seen_articles.setdefault(
                item["article_id"], {"item": item, "chunks": 0}
            )
            info["chunks"] += 1

        results = []
        for aid, info in seen_articles.items():
            if len(results) >= top_k:
                break
            item = info["item"]
            is_topic_article = (
                info["chunks"] >= 2
                or concept_hit(item["title_tokens"])
                or concept_hit(item["summary_tokens"])
                or item["similarity"] >= 0.15
            )
            if not is_topic_article:
                continue
            results.append({
                "article_id": aid,
                "title": item["title"],
                "slug": item["slug"],
                "summary": item["summary"],
                "similarity": item["similarity"],
                "matched_snippet": item["content"][:200] + "..."
            })

        # 批量补齐文章元数据（浏览/点赞/发布时间），供前端「最新/热门」排序展示
        if results:
            meta_rows = (
                db.query(Article.id, Article.views_count, Article.likes_count, Article.created_at)
                .filter(Article.id.in_([r["article_id"] for r in results]))
                .all()
            )
            meta = {row[0]: row for row in meta_rows}
            for r in results:
                row = meta.get(r["article_id"])
                if row:
                    r["views_count"] = row[1] or 0
                    r["likes_count"] = row[2] or 0
                    r["created_at"] = row[3]

        return results

    async def stream_rag_chat(
        self,
        db: Session,
        question: str,
        history: List[Dict[str, str]],
        user_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        RAG 知识库问答核心引擎 (全链路 SSE 流式生成 + 知识溯源)
        """
        # 1. 检索与读者提问最相关的博文切片
        snapshot = retrieval_index.get_snapshot(db)
        retrieved_chunks: List[Dict[str, Any]] = []
        if snapshot.size:
            retrieved_chunks = snapshot.search(
                query_sparse=get_sparse_embedding(question),
                query_text=question,
                # 扩大召回池：按文章去重后仍需凑齐 3 篇不同来源的引用
                top_k=max(settings.RAG_TOP_K * 2, 8),
                threshold=settings.RAG_SIMILARITY_THRESHOLD
            )

        # 2. 组装溯源引用卡片：同一篇文章仅保留相关度最高的一条切片，跨文章取前 3 篇
        citations = []
        seen_article_ids = set()
        for item in retrieved_chunks:
            if item["article_id"] in seen_article_ids:
                continue
            seen_article_ids.add(item["article_id"])
            citations.append({
                "citation_index": len(citations) + 1,
                "chunk_id": item["chunk_id"],
                "article_id": item["article_id"],
                "article_title": item["title"],
                "article_slug": item["slug"],
                "similarity": item["similarity"],
                "snippet": item["content"][:160] + "..."
            })
            if len(citations) >= 3:
                break

        # 上下文注入保持原策略：取相关度最高的 RAG_TOP_K 个切片 (允许同文多段)，保证回答信息量
        context_blocks = [
            f"【博文片段 {idx} (来自: 《{item['title']}》)】:\n{item['content']}"
            for idx, item in enumerate(retrieved_chunks[:settings.RAG_TOP_K], start=1)
        ]

        context_text = "\n\n".join(context_blocks)

        # 3. 构造强化 Prompt (带 Persona、知识边界、防幻觉机制)
        system_prompt = (
            "你是 AI博客论坛 的知识库智能助手。\n"
            "你的职责：友好、专业、清晰地向读者解答有关软件工程、AI 算法、大模型和论坛技术内容的问题。\n"
            "原则要求：\n"
            "1. 充分依据下方提供的【参考博文知识库片段】进行回答，言简意赅，逻辑清晰，排版格式良好（使用 Markdown）；\n"
            "2. 如果参考片段中包含答案，请自然融入回答，并在合适处引用博文观点；\n"
            "3. 如果问题超出了博文知识库范围，基于你作为AI算法工程师的技术知识给予严谨且具有指导性的专业回答，并坦诚指出该内容尚未在论坛中成文发布；\n"
            "4. 严禁无中生有编造论坛中不存在的事实；\n"
            "5. 直接回答问题正文，禁止自我介绍、禁止提及或自称任何名字（如「我是小智」），禁止重复开场白。\n\n"
            f"【参考博文知识库片段】:\n{context_text if context_text else '（暂无直接相关的博文切片）'}"
        )

        messages = [{"role": "system", "content": system_prompt}]

        # 拼接最近历史会话
        for h in history[-4:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

        messages.append({"role": "user", "content": question})

        full_reply_tokens: List[str] = []

        # 4. 流式生成 Token 并封装 SSE 协议包
        async for token in self.llm.stream_chat(messages):
            full_reply_tokens.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

        # 5. 生成结束后，发射引用溯源元数据包
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations}, ensure_ascii=False)}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

        # 6. 已登录账号对话自动持久化至用户专属历史记录
        if user_id:
            try:
                full_reply = "".join(full_reply_tokens).strip()
                from datetime import datetime
                from app.core.database import SessionLocal
                from app.models.ai_chat_message import AiChatMessage

                with SessionLocal() as db_session:
                    user_msg = AiChatMessage(
                        user_id=user_id,
                        role="user",
                        content=question,
                        created_at=datetime.utcnow()
                    )
                    asst_msg = AiChatMessage(
                        user_id=user_id,
                        role="assistant",
                        content=full_reply,
                        citations=json.dumps(citations, ensure_ascii=False) if citations else None,
                        created_at=datetime.utcnow()
                    )
                    db_session.add_all([user_msg, asst_msg])
                    db_session.commit()
            except Exception as e:
                logger.error(f"持久化 AI 对话历史失败: {e}")


rag_service = RAGService()
