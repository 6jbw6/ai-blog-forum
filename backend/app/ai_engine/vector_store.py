"""
检索数学层：稀疏向量空间下的余弦相似度、查询覆盖率与 BM25 饱和映射。

架构演进（2026-09-20）：

1. 向量表示由「稠密定长数组」切换为「稀疏非零项 + CSC 列压缩」。评分数学与旧稠密
   链路严格等价（L2 归一化行的点积即余弦，零填充不改变结果），但单次计算从
   O(词表维度) 降为 O(命中词元的倒排链长度)，且词表扩容不再改变向量体积。
2. 打分由「整条稀疏 matmul」改为「按查询词元遍历倒排链」：10 万切片 / 1200 万非零项
   实测整条 matmul 单次 15~35ms，而查询通常只命中十余个词元、其倒排链总长不足全库
   非零项的 5%，改法把 10 万切片下的单次检索压到 4~16ms。
3. BM25 由 rank_bm25 换为本模块的 Bm25Index。rank_bm25 为每条切片永久保留一张
   词频字典（实测约 9KB/切片，10 万切片即 0.9GB），且每个查询词元都要重跑一遍
   O(切片总数) 的 Python 循环 —— 万级切片下内存与延迟双双失控。Bm25Index 自建
   一套 CSC 倒排做向量化累加，得分与 rank_bm25 逐元素等价。

融合排序与召回门控逻辑见 retrieval_index.IndexSnapshot.search。
"""
from collections import Counter
from itertools import chain
from typing import Dict, List, Mapping, Sequence, Tuple
import numpy as np
from scipy import sparse as sp


# 覆盖率门控的主阈值：查询词元被切片覆盖过半即认为「这块内容确实在讲查询问的东西」。
# 取 0.5 而非 1.0 是为了容忍分词误差（如 "低秩自适应" 被 jieba 切成 低/秩自/适应，
# 其中 "秩自" 未登录），避免单个错分词元把整条正确结果否决。
MIN_QUERY_COVERAGE = 0.5

# 绝对分数兜底：覆盖率达标后再过一道数值噪声过滤，避免命中了但几乎无实质重叠的切片。
# 取值远低于 RAG_SIMILARITY_THRESHOLD，因为主判据已是覆盖率，这里只兜底不设卡。
MIN_ABS_SCORE = 0.03

# 标题命中加成系数：查询实义词出现在文章标题中是强相关信号（用户搜「显存 微调」，
# 标题同时含这两词的文章应排到纯正文命中的文章之前）。final × (1 + 0.25 × 命中比例)，
# 标题全命中即 ×1.25。只作用于门控之后的排序，不改变覆盖率门控判据。
TITLE_MATCH_BOOST = 0.25

# 查询侧问句虚词表（2026-09-20 修复）：自然语言问句里的疑问代词/否定词/语气词
# （如何、不够、怎么……）在这批技术语料中几乎不出现，IDF 反而虚高——覆盖率是
# IDF 加权的，这类「语料稀有虚词」会撑大分母，把真正讲「显存 微调」的文章
# （覆盖率 0.28）挡在门外，而恰好引用了「显存不够」短语的文章（覆盖率 0.60）
# 反被误放行。仅过滤查询侧：语料侧分词与已落库 TF-IDF 向量绝不动，词表维度不变。
QUERY_STOPWORDS = frozenset({
    # 疑问代词/副词
    "什么", "哪些", "哪个", "哪里", "哪儿", "怎样", "怎么样", "怎么", "如何", "为何",
    "为什么", "啥", "几", "几个", "多少", "几时",
    # 否定/情态/程度虚词
    "不", "不够", "不足", "没", "没有", "没法", "无法", "是否", "能否", "可以", "应该",
    # 语气助词与口语连接词
    "吗", "呢", "吧", "啊", "呀", "嘛", "么", "哦", "哈", "嗯",
    "请问", "请教", "想问", "我想", "帮我", "帮忙", "一下", "时候",
    # 指代与连接泛词
    "这个", "那个", "这些", "那些", "大家", "自己", "我们", "你们", "他们", "它们",
    "它", "他", "她", "其实", "然后", "还有", "以及",
    # 常见英文功能词（中英混合查询兜底）
    "what", "how", "why", "the", "a", "an", "of", "to", "is", "are",
})

# BM25 概率语义饱和映射系数：把无上界的 BM25 分数压缩到 [0, 1)，且不破坏相对排序。
# BM25 单次命中量级约 2~8，取 k=8 时常见命中落在 0.2~0.5，与稠密分数同量纲。
BM25_SATURATION_K = 8.0


def tokenize(text: str) -> List[str]:
    """
    统一分词入口：复用 embedding 的分词管道，保证 BM25 与稠密通道词元标准完全一致。

    延迟导入：本模块是纯数学层，import 期不应触发 TF-IDF 词表反序列化与 jieba 词典加载。
    """
    from app.ai_engine.embedding import _tokenize_text
    return _tokenize_text(text)


def strip_query_stopwords(query: str) -> str:
    """
    剥离查询中的问句虚词（疑问代词/否定词/语气词，见 QUERY_STOPWORDS）。

    仅用于查询侧（TF-IDF 查询向量、BM25 查询词元、覆盖率分母）：
    虚词在技术语料中稀有、IDF 虚高，会同时扭曲余弦分与覆盖率门控
    （详见 QUERY_STOPWORDS 注释）。语料侧分词与落库向量不受影响。
    过滤后全部词元被剥掉时原样返回，保证「怎么办」这类纯虚词查询不致误杀。
    """
    tokens = [t for t in tokenize(query) if t not in QUERY_STOPWORDS]
    return " ".join(tokens) if tokens else query


def dense_and_coverage_scores(
    chunk_matrix: sp.csc_matrix,
    query_sparse: Mapping[int, float],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    一次倒排链遍历同时产出两路分数：稠密通道余弦相似度 与 查询词元覆盖率。

    - 稠密路：切片行与查询向量都已 L2 归一化，逐维乘积之和即余弦。
      词频向量的余弦天然落在 [0, 1]（词重合度非负），直接裁剪即可；严禁使用
      (sim + 1) / 2 线性映射，该映射会把无关文本 0.1~0.2 的原始余弦虚高成
      55%~60% 的假相似度。
    - 覆盖率路：同一条倒排链只按查询权重累加一次「是否出现」，得到 IDF 加权的
      命中占比。它是「比例」量，分子分母同时随长度缩放，天然与切片长度、查询
      长度无关 —— 这是绝对阈值无法兼顾长短查询时引入它的原因（详见 2026-09-19
      实测：单字词查询 "RAG" 余弦仅 0.11 但覆盖率 1.0）。
      返回 [0, 1]：1.0 = 查询词元全部命中该切片；0.0 = 一个都没命中。
      注意：覆盖率只统计词表内词元，对未登录词 (OOV) 天然失明 —— 这一盲区
      由推荐服务的相关性门禁 (analyze_query_informativeness 主题词校验) 补齐。

    词表重建期间落库向量与当前词表可能短暂错位，越界列下标直接跳过而非整体报错。
    """
    n_docs, dim = chunk_matrix.shape
    dense = np.zeros(n_docs, dtype=np.float32)
    hits = np.zeros(n_docs, dtype=np.float32)

    terms = [(int(col), float(w)) for col, w in query_sparse.items() if 0 <= int(col) < dim and w > 0.0]
    q_total = sum(w for _, w in terms)
    if not terms or q_total <= 1e-8:
        return dense, hits

    indptr, rows_buf, data_buf = chunk_matrix.indptr, chunk_matrix.indices, chunk_matrix.data
    for col, weight in terms:
        start, end = indptr[col], indptr[col + 1]
        if start == end:
            continue
        rows = rows_buf[start:end]
        # 同一词元在一条切片中只有一条记录，rows 无重复，可安全做花式索引累加
        dense[rows] += weight * data_buf[start:end]
        hits[rows] += weight

    np.clip(dense, 0.0, 1.0, out=dense)
    return dense, np.clip(hits / q_total, 0.0, 1.0, out=hits)


def saturate_bm25(raw_scores: np.ndarray) -> np.ndarray:
    """
    BM25 分数的概率语义饱和映射 score/(score+k)，保留绝对量级信息。

    归一化会把每次检索得分最高的切片强行拉到 1.0，再经加权融合后，
    Top-1 的最终相似度会恒定虚高到 0.75 以上，展示给用户完全失真；
    饱和映射不破坏相对排序，且输出与稠密分数同量纲。
    """
    raw = np.clip(np.asarray(raw_scores, dtype=np.float32), 0.0, None)
    return raw / (raw + BM25_SATURATION_K)


class Bm25Index:
    """
    矩阵化的 Okapi BM25 倒排索引（k1=1.5, b=0.75, epsilon=0.25）

    与 rank_bm25.BM25Okapi 逐元素等价，差别只在存储与遍历方式：
    - 存储：(切片, 词元) -> 词频 的 CSC 稀疏矩阵，非零项即倒排链，
      不再为每个词元保留全库稠密数组，也不保留分词后的语料本身；
    - 查询：只遍历查询词元对应的倒排链，单次检索代价从
      O(查询词元数 × 切片总数) 降为 O(查询词元倒排链长度之和)。

    词频矩阵由 IndexSnapshot 在构建期一次性生成，随快照原子换装。
    """

    K1 = 1.5
    B = 0.75
    EPSILON = 0.25

    def __init__(self, postings: sp.csc_matrix, vocab: Dict[str, int],
                 doc_len: np.ndarray, idf: np.ndarray, avgdl: float):
        self._postings = postings
        self._vocab = vocab
        self._idf = idf
        # 长度归一化项只与切片长度有关，构建期算一次，查询期按行号取用
        self._len_norm = (
            self.K1 * (1.0 - self.B + self.B * doc_len / avgdl)
            if avgdl else np.zeros(doc_len.shape, dtype=np.float64)
        )

    @classmethod
    def build(cls, tokenized_corpus: Sequence[Sequence[str]]) -> "Bm25Index":
        n_docs = len(tokenized_corpus)
        doc_len = np.fromiter((len(t) for t in tokenized_corpus), dtype=np.float64, count=n_docs)
        total_tokens = int(doc_len.sum())

        if total_tokens == 0:
            # 空语料：无倒排可建，scores() 恒返回全零
            return cls(sp.csc_matrix((n_docs, 0), dtype=np.uint16), {}, doc_len, np.zeros(0), 0.0)

        vocab: Dict[str, int] = {}
        for tokens in tokenized_corpus:
            for token in tokens:
                if token not in vocab:
                    vocab[token] = len(vocab)

        term_codes = np.fromiter(
            map(vocab.__getitem__, chain.from_iterable(tokenized_corpus)),
            dtype=np.int32, count=total_tokens,
        )
        doc_rows = np.repeat(np.arange(n_docs, dtype=np.int32), doc_len.astype(np.int64))
        # COO -> CSC 会把同一 (切片, 词元) 的重复项求和，得到的即原始词频
        postings = sp.coo_matrix(
            (np.ones(total_tokens, dtype=np.uint16), (doc_rows, term_codes)),
            shape=(n_docs, len(vocab)),
        ).tocsc()

        # 文档频次 = 该词元的倒排链长度；Okapi idf 可为负（词元出现在过半切片中），
        # 按 rank_bm25 语义用 epsilon × 全词表平均 idf 兜底（均值须在兜底前统计）
        df = np.diff(postings.indptr).astype(np.float64)
        idf = np.log(n_docs - df + 0.5) - np.log(df + 0.5)
        idf = np.where(idf < 0.0, cls.EPSILON * float(idf.mean()), idf)

        return cls(postings, vocab, doc_len, idf, total_tokens / n_docs)

    def scores(self, query_tokens: Sequence[str]) -> np.ndarray:
        """查询词元列表 -> 每条切片的 BM25 分数（重复词元按出现次数累加，与 rank_bm25 一致）"""
        score = np.zeros(self._postings.shape[0], dtype=np.float64)
        if not query_tokens or not self._vocab:
            return score

        indptr, rows_buf, freq_buf = self._postings.indptr, self._postings.indices, self._postings.data
        for token, multiplicity in Counter(query_tokens).items():
            col = self._vocab.get(token)
            if col is None:
                continue
            weight = self._idf[col]
            if weight == 0.0:
                continue
            rows = rows_buf[indptr[col]:indptr[col + 1]]
            freq = freq_buf[indptr[col]:indptr[col + 1]].astype(np.float64)
            # 同一词元在一条切片中只出现一次记录，rows 无重复，可安全做花式索引累加
            score[rows] += multiplicity * weight * (freq * (self.K1 + 1.0)) / (
                freq + self._len_norm[rows]
            )
        return score
