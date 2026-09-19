from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity
from rank_bm25 import BM25Okapi
import jieba


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    基于 Scikit-Learn 官方标准库计算两个特征向量的余弦相似度 (Cosine Similarity)

    文本词频特征向量的夹角余弦天然落在 [0, 1] 语义区间（词重合度非负），
    直接裁剪到 [0, 1] 即可；严禁使用 (sim + 1) / 2 线性映射，该映射会把
    无关文本 0.1~0.2 的原始余弦虚高成 55%~60% 的假相似度。
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    arr_a = np.array(vec_a, dtype=np.float32).reshape(1, -1)
    arr_b = np.array(vec_b, dtype=np.float32).reshape(1, -1)

    sim = float(sklearn_cosine_similarity(arr_a, arr_b)[0][0])
    return max(0.0, min(1.0, sim))


def calculate_bm25_scores(query: str, texts: List[str], query_tokens: List[str] = None) -> np.ndarray:
    """
    基于行业标准 rank-bm25 与 Jieba 中文分词计算 BM25 稀疏检索相关度得分

    返回值为「绝对相关度」而非 Min-Max 归一化值：
    归一化会把每次检索得分最高的切片强行拉到 1.0，再经加权融合后，
    Top-1 的最终相似度会恒定虚高到 0.75 以上，展示给用户完全失真。
    这里改用概率语义饱和映射 score/(score+k)，保留绝对量级信息。
    """
    if not texts or not query.strip():
        return np.zeros(len(texts), dtype=np.float32)

    tokenizer = _shared_tokenizer()

    # 1. 中文分词构建词袋语料库
    tokenized_corpus = [tokenizer._tokenize(t) for t in texts]
    tokenized_query = query_tokens if query_tokens is not None else tokenizer._tokenize(query)

    if not tokenized_query or not any(tokenized_corpus):
        return np.zeros(len(texts), dtype=np.float32)

    # 2. 调用标准 BM25Okapi 算法
    bm25 = BM25Okapi(tokenized_corpus)
    raw_scores = np.array(bm25.get_scores(tokenized_query), dtype=np.float32)
    raw_scores = np.clip(raw_scores, 0.0, None)

    # 3. 概率语义饱和映射：把无上界的 BM25 分数压缩到 [0, 1)，且不破坏相对排序
    #    BM25 单次命中量级约 2~8，取 k=8 时常见命中落在 0.2~0.5，与稠密分数同量纲
    saturation_k = 8.0
    return raw_scores / (raw_scores + saturation_k)


_BM25_TOKENIZER = None


def _shared_tokenizer():
    """复用 embedding 模块的分词器，保证稀疏路与稠密路词元标准完全一致"""
    global _BM25_TOKENIZER
    if _BM25_TOKENIZER is None:
        from app.ai_engine.embedding import LocalSemanticEmbedder
        _BM25_TOKENIZER = LocalSemanticEmbedder()
    return _BM25_TOKENIZER


def compute_query_coverage(query_vec: List[float], chunk_matrix: np.ndarray) -> np.ndarray:
    """
    查询词元在切片中的 IDF 加权「覆盖率」——与长度无关的相关性判据

    为什么必须引入它（2026-09-19 实测，3 篇博文 / 18 切片）：
    余弦相似度会同时被「查询长度」和「切片长度」摊薄。切片是 450 字长文本，
    TF-IDF 向量有数百个非零维度，查询只有 1~2 个词元时，分母（切片向量范数）
    把分数压到 0.11~0.14；而 3 词以上查询可达 0.24~0.40。于是同一个绝对阈值
    必然两头不讨好：卡 0.18 会把 "RAG" 的正确结果直接滤掉，放宽又会放进噪声。

    曾用「按查询长度打折阈值」来补偿，实测暴露出非单调缺陷：
    "RAG" 0.1102 过 0.108 放行，而更具体的 "RAG 知识库" 分数更高（0.1372）
    却因阈值跳到 0.153 被拒 —— 查询变长、相关性变强，反而搜不到。

    覆盖率是「比例」量，分子分母同时随长度缩放，天然与切片长度、查询长度无关，
    语义也明确：查询里问的东西，这个切片覆盖了多少。
    权重直接复用查询向量的 TF-IDF 值（已 L2 归一化），因此与稠密通道严格同空间，
    且无需重新分词、无额外开销。

    返回 [0, 1]：1.0 = 查询词元全部命中该切片；0.0 = 一个都没命中
    （查询词全部是未登录词时查询向量为全零，此时同样返回 0，天然拒绝 OOV 查询）。
    """
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    nz = np.nonzero(q)[0]
    if nz.size == 0:
        return np.zeros(chunk_matrix.shape[0], dtype=np.float32)

    weights = np.abs(q[nz])
    total = float(weights.sum())
    if total <= 1e-8:
        return np.zeros(chunk_matrix.shape[0], dtype=np.float32)

    hits = (chunk_matrix[:, nz] > 0).astype(np.float32)
    return (hits @ weights) / total


# 覆盖率门控的主阈值：查询词元被切片覆盖过半即认为「这块内容确实在讲查询问的东西」。
# 取 0.5 而非 1.0 是为了容忍分词误差（如 "低秩自适应" 被 jieba 切成 低/秩自/适应，
# 其中 "秩自" 未登录），避免单个错分词元把整条正确结果否决。
MIN_QUERY_COVERAGE = 0.5

# 绝对分数兜底：覆盖率达标后再过一道数值噪声过滤，避免命中了但几乎无实质重叠的切片。
# 取值远低于 RAG_SIMILARITY_THRESHOLD，因为主判据已是覆盖率，这里只兜底不设卡。
MIN_ABS_SCORE = 0.03


def hybrid_search(
    query_vec: List[float],
    query_text: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 4,
    threshold: float = 0.30,
    dense_weight: float = 0.75,
    sparse_weight: float = 0.25,
    min_coverage: float = MIN_QUERY_COVERAGE
) -> List[Dict[str, Any]]:
    """
    工业级多路召回与混合重排检索器 (Hybrid Dense-Sparse Reranking)

    架构依赖:
    - 稠密向量计算: Scikit-Learn 矩阵级余弦相似度批量计算；
    - 稀疏关键词计算: Jieba 分词 + Rank-BM25 (BM25Okapi) 工业级文本检索模型；
    - 融合策略: 标准化评分融合矩阵 (Dense Weight + BM25 Weight)；
    - 召回门控: 查询词元覆盖率（主）+ 绝对融合分（辅），见 compute_query_coverage。

    召回判据（两条满足其一即可进入候选，再过一道绝对分兜底）:
    1. 覆盖率 >= min_coverage：切片确实覆盖了查询里问的内容。这是主判据，
       用于救回被长切片摊薄的短查询/主题词查询（如 "RAG"、"BM25"）。
    2. 融合分 >= threshold：词法重叠本身足够强。保留这条是为了不破坏
       原本靠高分召回的长查询路径。

    评分语义:
    `similarity` 是「词法重叠度」的加权融合值，量纲与余弦相似度一致、落在 [0, 1]，
    可直接作为百分比展示；但它衡量的是关键词重合，不是人类直觉上的「语义一致度」。
    门控改用覆盖率后，**展示值仍是不加修饰的原始融合分**，不做任何拉伸或归一化。
    """
    if not chunks:
        return []

    # 1. 稠密向量矩阵级快速内积计算 (利用 Scikit-Learn 优化底层 BLAS)
    query_matrix = np.array([query_vec], dtype=np.float32)
    chunk_vectors = np.array([item["embedding"] for item in chunks], dtype=np.float32)

    # 0. 覆盖率：与稠密通道共享同一向量空间，无需重新分词
    coverage = compute_query_coverage(query_vec, chunk_vectors)

    dense_sims = sklearn_cosine_similarity(query_matrix, chunk_vectors)[0]
    # 词频向量的余弦相似度天然位于 [0, 1]，直接裁剪；不做 (sim+1)/2 映射避免无关文本相似度虚高
    dense_scores = np.clip(dense_sims, 0.0, 1.0)

    # 2. 稀疏检索：调用 Rank-BM25 计算关键词精准度
    chunk_contents = [item["content"] for item in chunks]
    sparse_scores = calculate_bm25_scores(query_text, chunk_contents)

    # 3. 混合加权得分计算
    scored_results = []
    for idx, item in enumerate(chunks):
        dense_score = float(dense_scores[idx])
        sparse_score = float(sparse_scores[idx])

        final_score = (dense_score * dense_weight) + (sparse_score * sparse_weight)

        # 召回门控：覆盖率达标（主）或融合分达标（辅），再统一过数值噪声兜底
        if final_score < MIN_ABS_SCORE:
            continue
        if float(coverage[idx]) < min_coverage and final_score < threshold:
            continue

        scored_results.append({
            **item,
            "similarity": round(final_score, 4),
            "dense_score": round(dense_score, 4),
            "sparse_score": round(sparse_score, 4),
            "coverage": round(float(coverage[idx]), 4)
        })

    # 按综合得分降序排列并截取 Top-K
    scored_results.sort(key=lambda x: x["similarity"], reverse=True)
    return scored_results[:top_k]
