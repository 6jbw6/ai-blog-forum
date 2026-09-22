"""
稀疏检索内存索引 (Sparse Retrieval Index)

架构演进（2026-09-20）：旧实现每次查询都从 MySQL 全量加载切片、逐条 JSON 解析
稠密向量并现场重建 BM25 索引 —— 千级切片时单次查询即达秒级，万级博文不可用。

本模块把检索态收敛为一份进程内不可变快照 (IndexSnapshot)，并让快照的整个生命周期
都不出现在请求线程里：
- 切片稀疏向量预拼装为 CSC 倒排，稠密余弦、覆盖率与 BM25 三路打分都只遍历查询
  词元命中的倒排链，不再逐查询重建任何索引；
- 轻量版本指纹 (切片总数/最大ID/发布文章数) 按最小间隔节流探测，命中变更后由
  后台线程重建，请求线程继续用旧快照服务，既无空窗也不承担重建耗时；
- 快照整体只读、原子替换，天然支持多线程并发检索 (FastAPI 线程池)。

实测规模参考（10 万切片 / 1220 万非零项 / 15 万词表，合成语料，本机实测）：
检索态常驻约 180MB（TF-IDF CSC 98MB + BM25 倒排 74MB + 词表字典与长度数组约 11MB）；
矩阵装配 2s + BM25 构建 8s，另需 jieba 全量分词约 1 分钟（实测 1500 切片/秒），
全程在后台线程完成；单次检索 4~16ms（1~20 词元，查询词按 Zipf 抽样刻意含最长倒排链）。
"""
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import sparse as sp
from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.ai_engine.embedding import (
    _local_embedder,
    json_to_sparse_vector,
)
from app.ai_engine.vector_store import (
    MIN_ABS_SCORE,
    MIN_QUERY_COVERAGE,
    TITLE_MATCH_BOOST,
    Bm25Index,
    dense_and_coverage_scores,
    saturate_bm25,
    strip_query_stopwords,
    tokenize,
)

logger = logging.getLogger("app.retrieval_index")

# 版本指纹的最小探测间隔（秒）。
# 指纹是三条 COUNT(*)，若每次检索都读一遍，检索热路径就重新绑上了数据库往返；
# 节流后万级 QPS 量级下探测成本恒定，而发文带来的新鲜度延迟已由 invalidate() 主动失效兜住。
VERSION_CHECK_INTERVAL = 10.0


@dataclass
class IndexSnapshot:
    """一份只读检索快照：切片元数据 + TF-IDF 倒排 + BM25 倒排"""
    chunk_ids: np.ndarray
    article_ids: np.ndarray
    titles: List[str]
    slugs: List[str]
    summaries: List[str]
    contents: List[str]
    matrix: sp.csc_matrix
    bm25: Optional[Bm25Index]
    # 标题/摘要词元集合（构建期预分词），供查询期标题命中加成与文章级主题判定零开销取用
    title_tokens: List[frozenset]
    summary_tokens: List[frozenset]
    version: tuple = ()
    built_at: float = 0.0
    size: int = field(init=False)

    def __post_init__(self):
        self.size = len(self.titles)

    def search(
        self,
        query_sparse: Dict[int, float],
        query_text: str,
        top_k: int = 4,
        threshold: float = 0.30,
        dense_weight: float = 0.75,
        sparse_weight: float = 0.25,
        min_coverage: float = MIN_QUERY_COVERAGE,
    ) -> List[Dict[str, Any]]:
        """
        混合多路召回与重排 (Hybrid Dense-Sparse Reranking)，评分语义与旧稠密链路完全一致：
        - 稠密路：稀疏 TF-IDF 行已 L2 归一化，逐维乘积和即余弦相似度；
        - 稀疏路：BM25 绝对分数经概率饱和映射 score/(score+k)，与稠密分同量纲；
        - 查询净化：BM25 查询词元同样剥离问句虚词（如何/不够……），与稠密路
          的 get_sparse_embedding 净化标准一致，虚词不再给「引用了问句短语」的
          巧合切片送 BM25 分；
        - 召回门控：查询词元覆盖率（主）或融合分（辅）满足其一，再过绝对分兜底；
        - 标题加成：门控通过后，查询实义词在文章标题中的命中比例乘上
          (1 + TITLE_MATCH_BOOST × 比例)，仅影响排序与最终展示分，不动门控判据。

        门控与 Top-K 选取全程向量化：先用一条布尔掩码筛出合格切片，再只对合格项做
        argpartition 部分选择。这既避开了 O(N log N) 的全量排序和逐条 Python 循环，
        又与「先过滤再取前 k」的原始语义严格等价。
        """
        if self.size == 0:
            return []

        dense_scores, coverage = dense_and_coverage_scores(self.matrix, query_sparse)

        query_tokens = tokenize(strip_query_stopwords(query_text))
        if self.bm25 is not None and query_tokens:
            sparse_scores = saturate_bm25(self.bm25.scores(query_tokens))
        else:
            sparse_scores = np.zeros(self.size, dtype=np.float32)

        final_scores = dense_scores * dense_weight + sparse_scores * sparse_weight

        eligible = np.flatnonzero(
            (final_scores >= MIN_ABS_SCORE)
            & ((coverage >= min_coverage) | (final_scores >= threshold))
        )
        if eligible.size == 0:
            return []

        # 标题命中加成（门控之后）：查询实义词出现在标题中的文章相关度更强，
        # 典型场景——搜「显存 微调」时标题即含两词的 LoRA 文章应排在仅在正文
        # 巧合引用了「显存不够」的文章之前。分母取 len(query_tokens) 而非词表，
        # 未登录词 (OOV) 不参与加成，与覆盖率对齐。
        q_token_set = set(query_tokens)
        if q_token_set:
            boosts = np.ones(self.size, dtype=np.float32)
            for idx in eligible:
                hits = len(q_token_set & self.title_tokens[idx])
                boosts[idx] = 1.0 + TITLE_MATCH_BOOST * (hits / len(q_token_set))
            final_scores = final_scores * boosts

        k = min(top_k, eligible.size)
        if k < eligible.size:
            eligible = eligible[np.argpartition(-final_scores[eligible], k - 1)[:k]]
        picked = eligible[np.argsort(-final_scores[eligible], kind="stable")]

        return [{
            "chunk_id": int(self.chunk_ids[idx]),
            "article_id": int(self.article_ids[idx]),
            "title": self.titles[idx],
            "slug": self.slugs[idx],
            "summary": self.summaries[idx],
            "content": self.contents[idx],
            "similarity": round(float(final_scores[idx]), 4),
            "dense_score": round(float(dense_scores[idx]), 4),
            "sparse_score": round(float(sparse_scores[idx]), 4),
            "coverage": round(float(coverage[idx]), 4),
            # 词元集合按引用透传（frozenset 零拷贝），供文章级主题判定使用
            "title_tokens": self.title_tokens[idx],
            "summary_tokens": self.summary_tokens[idx],
        } for idx in picked]


class SparseRetrievalIndex:
    """
    进程级检索索引管理器：冷启动预热 + 节流变更探测 + 单飞后台重建

    三条不变量：
    1. 请求线程永不重建索引（冷启动首个请求除外，且该请求与预热线程共享同一次构建）；
    2. 任意时刻最多一个重建线程（发文风暴下不会重复全量加载）；
    3. 快照只读、整体原子替换，重建期间旧快照继续服务，检索无空窗。
    """

    def __init__(self):
        # _state_lock 只保护下面几个字段的读写，临界区内绝不做 IO
        self._state_lock = threading.Lock()
        # _build_lock 串行化真正的重建过程，保证同一份数据只加载一次
        self._build_lock = threading.Lock()
        self._snapshot: Optional[IndexSnapshot] = None
        self._version: Optional[tuple] = None
        self._rebuilding = False
        self._last_check = 0.0

    def get_snapshot(self, db) -> IndexSnapshot:
        """取当前可用快照；发现语料已变更时触发后台重建，本次仍返回旧快照"""
        snapshot = self._snapshot
        if snapshot is None:
            return self._build_blocking()
        if self._version_changed(db):
            self._schedule_rebuild()
        return snapshot

    def warmup(self) -> None:
        """应用启动时调用：后台线程预热首份快照，不阻塞服务启动"""
        self._schedule_rebuild()

    def invalidate(self) -> None:
        """
        索引内容变更后调用（发文、删文、全量重建）。

        把指纹置为「必然不匹配」并解除节流，下一次检索即触发后台重建；
        不直接重建是因为这里通常持有写事务的会话，重建需要独立的读会话。
        """
        with self._state_lock:
            self._version = None
            self._last_check = 0.0

    def _schedule_rebuild(self) -> None:
        with self._state_lock:
            if self._rebuilding:
                return
            self._rebuilding = True
        threading.Thread(
            target=self._rebuild_in_background,
            name="retrieval-index-rebuild",
            daemon=True,
        ).start()

    def _rebuild_in_background(self) -> None:
        """后台线程必须自建会话：SQLAlchemy Session 不是线程安全的，绝不能复用请求会话"""
        try:
            self._install(force=True)
        except Exception as e:
            logger.error(f"检索索引后台重建失败，继续使用上一份快照: {e}")
        finally:
            with self._state_lock:
                self._rebuilding = False

    def _build_blocking(self) -> IndexSnapshot:
        """冷启动路径：当前线程等待快照就绪；与预热线程并发时共用同一次构建结果"""
        if self._snapshot is None:
            self._install()
        return self._snapshot

    def _install(self, force: bool = False) -> None:
        """
        构建并原子发布一份新快照。

        _build_lock 保证同一时刻只有一处在加载全量数据；force=False 时进入锁后
        再次确认快照仍为空，避免冷启动线程与预热线程重复构建。
        """
        with self._build_lock:
            if not force and self._snapshot is not None:
                return
            started = time.perf_counter()
            with SessionLocal() as db:
                snapshot = self._build_snapshot(db)
            with self._state_lock:
                self._snapshot = snapshot
                self._version = snapshot.version
                self._last_check = time.monotonic()
            logger.info(
                f"检索索引已就绪：{snapshot.size} 个切片 / {snapshot.matrix.nnz} 个非零项 / "
                f"耗时 {time.perf_counter() - started:.2f}s"
            )

    def _version_changed(self, db) -> bool:
        """按最小间隔节流地比对版本指纹；invalidate() 后首次调用必定判定为已变更"""
        now = time.monotonic()
        with self._state_lock:
            expected = self._version
            if now - self._last_check < VERSION_CHECK_INTERVAL:
                return False
            self._last_check = now
        return self._read_version(db) != expected

    def _read_version(self, db) -> tuple:
        """轻量版本指纹：三次标量计数即可感知切片增删与发布状态变化，代价远低于全量加载"""
        row = db.execute(text(
            "SELECT "
            "(SELECT COUNT(*) FROM article_chunks) AS chunk_total, "
            "(SELECT COALESCE(MAX(id), 0) FROM article_chunks) AS chunk_max_id, "
            "(SELECT COUNT(*) FROM articles WHERE is_published = 1 AND is_private = 0) AS article_total"
        )).fetchone()
        return (int(row[0]), int(row[1]), int(row[2]))

    def _build_snapshot(self, db) -> IndexSnapshot:
        """从数据库加载全部已发布切片，构建 CSR 稀疏矩阵、二值矩阵与 BM25 倒排（纯读操作）"""
        # 指纹必须在加载数据「之前」读取：先读后载最坏只是多重建一次（可收敛），
        # 反过来则可能拿到比数据更新的指纹，把新发文永久判定为已索引。
        version = self._read_version(db)
        rows = (
            db.query(
                ArticleChunk.id,
                ArticleChunk.article_id,
                ArticleChunk.content,
                ArticleChunk.embedding_json,
                Article.title,
                Article.slug,
                Article.summary,
            )
            .join(Article, ArticleChunk.article_id == Article.id)
            .filter(Article.is_published == True, Article.is_private == False)
            .order_by(ArticleChunk.article_id, ArticleChunk.chunk_index)
            .all()
        )

        titles: List[str] = []
        slugs: List[str] = []
        summaries: List[str] = []
        contents: List[str] = []
        chunk_ids: List[int] = []
        article_ids: List[int] = []
        coo_rows: List[int] = []
        coo_cols: List[int] = []
        coo_vals: List[float] = []

        # 词表规模以「当前词表」与「落库向量实际用到的最大下标」取大：
        # 词表重建期间两者可能短暂错位，若直接按词表长度建矩阵会因列下标越界整体报错。
        vocab = getattr(_local_embedder.vectorizer, "vocabulary_", None)
        dim = len(vocab) if vocab else 0
        for row_idx, (cid, aid, content, emb_json, title, slug, summary) in enumerate(rows):
            vec = json_to_sparse_vector(json.loads(emb_json))
            for col, val in vec.items():
                coo_rows.append(row_idx)
                coo_cols.append(int(col))
                coo_vals.append(float(val))
            chunk_ids.append(cid)
            article_ids.append(aid)
            titles.append(title)
            slugs.append(slug)
            summaries.append(summary or "")
            contents.append(content)

        matrix = sp.coo_matrix(
            (np.asarray(coo_vals, dtype=np.float32),
             (np.asarray(coo_rows, dtype=np.int32), np.asarray(coo_cols, dtype=np.int32))),
            shape=(max(len(rows), 1), max(dim, max(coo_cols, default=-1) + 1, 1)),
        ).tocsc()

        return IndexSnapshot(
            chunk_ids=np.asarray(chunk_ids, dtype=np.int64),
            article_ids=np.asarray(article_ids, dtype=np.int64),
            titles=titles,
            slugs=slugs,
            summaries=summaries,
            contents=contents,
            matrix=matrix,
            bm25=Bm25Index.build([tokenize(c) for c in contents]) if contents else None,
            # 标题/摘要构建期分词一次：查询期标题加成直接集合求交、
            # 文章级主题判定直接取用，均无运行时开销
            title_tokens=[frozenset(tokenize(t)) for t in titles],
            summary_tokens=[frozenset(tokenize(s)) for s in summaries],
            version=version,
            built_at=time.time(),
        )


retrieval_index = SparseRetrievalIndex()
