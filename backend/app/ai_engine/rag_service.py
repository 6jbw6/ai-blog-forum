import json
from typing import List, Dict, Any, AsyncGenerator, Optional
from sqlalchemy.orm import Session
from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.ai_engine.chunking import MarkdownChunker
from app.ai_engine.embedding import get_embedding, get_embeddings, fit_embedding_corpus
from app.ai_engine.vector_store import hybrid_search
from app.ai_engine.llm_client import UnifiedLLMClient
from app.core.config import settings
import logging

logger = logging.getLogger("app.rag")


class RAGService:
    """
    RAG (检索增强生成) 全生命周期服务体系
    
    架构全流程:
    1. 知识录入阶段 (Ingestion): Markdown 解析 -> 语义感知识别切块 -> TF-IDF 特征向量化 -> MySQL 切片持久化
    2. 检索阶段 (Retrieval): 用户 Query 向量化 -> 多路召回与混合加权排序 -> 提取 Top-K 知识切片
    3. 上下文合成 (Augmentation): 注入博主 Persona、防幻觉提示词与知识溯源锚点
    4. 生成阶段 (Generation): 大模型流式输出 (SSE) + 结构化引用卡片直达联动
    """

    def __init__(self):
        self.chunker = MarkdownChunker(target_chunk_size=450, chunk_overlap=60)
        self.llm = UnifiedLLMClient()

    def index_article(self, db: Session, article_id: int) -> int:
        """为单篇文章构建向量索引切片"""
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article or not article.content:
            return 0

        # 1. 标题感知递归切块
        raw_chunks = self.chunker.split_text(article.title, article.content)
        
        # 2. 清理旧切片
        db.query(ArticleChunk).filter(ArticleChunk.article_id == article_id).delete()

        # 3. 批量生成向量并存储 (一次矩阵变换，避免逐条 transform 的重复开销)
        contents = [item["content"] for item in raw_chunks]
        embeddings = get_embeddings(contents)
        chunk_objects = []
        for idx, item in enumerate(raw_chunks):
            chunk_obj = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                chunk_title=item.get("title", article.title),
                content=item["content"],
                embedding_json=json.dumps(embeddings[idx]),
                token_count=item.get("token_count", len(item["content"]))
            )
            chunk_objects.append(chunk_obj)

        db.add_all(chunk_objects)
        article.vector_status = "indexed"
        db.commit()

        logger.info(f"Article '{article.title}' (ID: {article.id}) indexed successfully with {len(chunk_objects)} chunks.")
        return len(chunk_objects)

    def reindex_all_articles(self, db: Session) -> Dict[str, int]:
        """
        全量重建所有已发布博文的向量索引

        两阶段执行：先对全量切片拟合 TF-IDF 词表/IDF（全局统计），再统一编码落库，
        避免逐篇编码时 IDF 只反映单篇内容导致权重失真。
        """
        articles = db.query(Article).filter(Article.is_published == True).all()

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
            embeddings = get_embeddings([item["content"] for item in raw_chunks])
            db.add_all([
                ArticleChunk(
                    article_id=art.id,
                    chunk_index=idx,
                    chunk_title=item.get("title", art.title),
                    content=item["content"],
                    embedding_json=json.dumps(embeddings[idx]),
                    token_count=item.get("token_count", len(item["content"]))
                )
                for idx, item in enumerate(raw_chunks)
            ])
            art.vector_status = "indexed"
            total_chunks += len(raw_chunks)

        db.commit()
        logger.info(f"全量向量重构完成：{len(articles)} 篇博文 / {total_chunks} 个切片")
        return {"articles_indexed": len(articles), "total_chunks": total_chunks}

    def semantic_search(self, db: Session, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """自然语言语义检索 (突破传统关键词硬匹配)"""
        # 1. 向量化用户 Query
        query_vec = get_embedding(query)

        # 2. 读取所有已发布文章的切片
        chunks = (
            db.query(ArticleChunk, Article.title, Article.slug, Article.summary)
            .join(Article, ArticleChunk.article_id == Article.id)
            .filter(Article.is_published == True)
            .all()
        )

        if not chunks:
            return []

        chunk_data = []
        for c, art_title, art_slug, art_summary in chunks:
            chunk_data.append({
                "chunk_id": c.id,
                "article_id": c.article_id,
                "title": art_title,
                "slug": art_slug,
                "summary": art_summary,
                "content": c.content,
                "embedding": json.loads(c.embedding_json)
            })

        # 3. 混合多路召回与重排
        scored = hybrid_search(
            query_vec=query_vec,
            query_text=query,
            chunks=chunk_data,
            top_k=top_k * 2,
            threshold=settings.RAG_SIMILARITY_THRESHOLD
        )

        # 4. 按文章去重聚合 (同一篇文章取相关度最高的一段)
        seen_articles = set()
        results = []
        for item in scored:
            art_id = item["article_id"]
            if art_id not in seen_articles:
                seen_articles.add(art_id)
                results.append({
                    "article_id": art_id,
                    "title": item["title"],
                    "slug": item["slug"],
                    "summary": item["summary"],
                    "similarity": item["similarity"],
                    "matched_snippet": item["content"][:200] + "..."
                })
            if len(results) >= top_k:
                break

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
        query_vec = get_embedding(question)

        chunks = (
            db.query(ArticleChunk, Article.title, Article.slug)
            .join(Article, ArticleChunk.article_id == Article.id)
            .filter(Article.is_published == True)
            .all()
        )

        retrieved_chunks: List[Dict[str, Any]] = []
        if chunks:
            chunk_data = [{
                "chunk_id": c.id,
                "article_id": c.article_id,
                "title": art_title,
                "slug": art_slug,
                "content": c.content,
                "embedding": json.loads(c.embedding_json)
            } for c, art_title, art_slug in chunks]

            retrieved_chunks = hybrid_search(
                query_vec=query_vec,
                query_text=question,
                chunks=chunk_data,
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
