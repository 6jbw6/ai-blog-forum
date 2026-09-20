import json
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List
import numpy as np
import joblib
from scipy import sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from openai import AsyncOpenAI
import jieba
from app.core.config import settings

logger = logging.getLogger("app.embedding")

# 拟合后的 TF-IDF 词表/IDF 持久化路径。
# 关键：词表是全局统计量，只存在于执行「全量重建」的那个进程内存里。
# 若不落盘，服务一旦重启词表即丢失，查询只能"拿查询词自己拟合"，
# 查询向量与库内向量的维度语义完全错位，相似度沦为随机数（相关查询召回为 0）。
_VECTORIZER_PATH = Path(__file__).resolve().parent / "tfidf_vectorizer.joblib"

# 词表软上限（仅约束内存，不再约束向量长度）。
#
# 架构演进（2026-09-20）：早期向量以「稠密定长数组」落库，维度必须恒定，
# 词表按词频截断到 EMBEDDING_DIM，语料增长后高频泛词挤占预算、低频高区分度的
# 专有名词（PagedAttention / AWQ 级别）被裁出词表，稠密检索对其彻底失效。
# 现已切换为稀疏表示：每条切片只存非零项 {词表下标: 权重}，向量体积与
# 「切片实际命中的词条数」（两三百个）挂钩，而与词表总规模彻底解耦——
# 词表上限不再参与存储成本，只用于约束词表字典自身的内存占用。
#
# 1_000_000 的取值依据：实测约 600 词条/篇（3 篇 1832 / 13 篇 7958），
# 考虑万级博文下主题重叠带来的次线性增长（Heaps 律），百万级词条足以
# 覆盖绝大多数语料；若未来触顶，仅需提高本值并执行一次全量重建。
MAX_VOCAB_SIZE = 1_000_000

# 高频虚词/标点：中文由 jieba 直接丢弃，英文靠停用词表丢弃
_STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "and", "or", "is", "are",
    "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
    "with", "as", "by", "from", "we", "you", "they", "he", "she", "i", "do", "does",
    "did", "not", "no", "but", "if", "then", "than", "so", "such", "can", "could",
    "will", "would", "should", "may", "might", "must", "have", "has", "had", "there",
    "here", "what", "which", "who", "whom", "when", "where", "why", "how", "all",
    "any", "both", "each", "more", "most", "other", "some", "only", "own", "same",
    "too", "very", "just", "also", "into", "over", "after", "before", "between",
    "up", "down", "out", "off", "about", "against", "because", "while", "during",
}
_STOPWORDS_CN = {
    "的", "了", "和", "是", "在", "我", "有", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "这个", "那个", "我们", "他们", "可以", "与", "及", "或",
    "而", "并", "并且", "但是", "因为", "所以", "如果", "因此", "以及", "对于",
    "关于", "通过", "进行", "以", "于", "中", "对", "为", "被", "把", "从", "等",
    "之", "其", "该", "此", "则", "且", "亦", "即", "其", "上述", "如下", "以下",
}
_FILTERED = _STOPWORDS | _STOPWORDS_CN

# 通用词频泛词阈值：jieba 词典词频高于该值的词元视为「框架泛词」（怎么做/什么/想/系统/实现等），
# 不携带主题信息。校准依据（2026-09-20 实测 jieba 通用词频）：
# 泛词集中在 1.5万+（做 50331、什么 59317、怎么 27339、想 61904、实现 15301、系统 20602），
# 主题词普遍在 1 万以下（红烧肉 58、量化 117、前端 312、原理 3267、股票 2923、文章 6728），
# 10_000 恰好分开两簇。技术专名（rag/qlora 等）不在通用词典中（FREQ 为 None），天然归为主题词。
_FREQ_FILLER_MIN = 10_000


def _tokenize_text(text: str) -> List[str]:
    """
    统一分词管道（模块级函数）：小写 -> jieba 中英混合切分 -> 去停用词/纯标点噪声

    必须保持模块级：TfidfVectorizer 会序列化 tokenizer 引用，
    模块级函数才能在服务重启后从磁盘词表正确反序列化。
    """
    if not text:
        return []
    cleaned = text.lower().strip()
    if not cleaned:
        return []
    tokens = []
    for w in jieba.lcut(cleaned):
        w = w.strip()
        if not w:
            continue
        if not re.search(r"[0-9a-z\u4e00-\u9fff]", w):
            continue
        if w in _FILTERED:
            continue
        # 纯数字丢弃：数字在技术文本中几乎无区分度，且极易与短英文词哈希碰撞
        if w.isdigit():
            continue
        tokens.append(w)
    return tokens


def sparse_vector_to_json(vec: Dict[int, float]) -> str:
    """稀疏向量 -> 紧凑 JSON（ids + vals 双数组），体积约为稠密定长 JSON 的 1/20"""
    ids = sorted(vec.keys())
    return json.dumps({"ids": ids, "vals": [round(vec[i], 6) for i in ids]}, separators=(",", ":"))


def json_to_sparse_vector(payload) -> Dict[int, float]:
    """解析落库的稀疏向量 JSON；出现旧版稠密格式时明确报错引导全量重建"""
    if isinstance(payload, dict) and "ids" in payload and "vals" in payload:
        return {int(i): float(v) for i, v in zip(payload["ids"], payload["vals"])}
    raise ValueError(
        "检测到旧版稠密向量格式，与当前稀疏检索引擎不兼容，请执行全量重建 (/ai/reindex-all)"
    )


class LocalSemanticEmbedder:
    """
    基于 Scikit-Learn 官方 TfidfVectorizer 的工业级词法相关度向量生成器（稀疏表示）

    为什么不用 HashingVectorizer（重要历史结论）：
    固定小维度的特征哈希会不可避免地把无关词元映射到同一位上。实测 128/256 维哈希下，
    查询 "vue" 仅占 1 个维度，语料里光是数字 "1" 就与它碰撞，直接产生 39% 的原始余弦、
    经加权融合后仍剩 25.8% —— 这正是「vue 和 LoRA 相似度 58%」的根因。
    哈希碰撞无法通过调维度根治，只有建立真实词表才能让维度语义一一对应。

    改用 TfidfVectorizer 后的三个收益：
    1. 维度语义确定：每个维度对应一个真实词元，不再有碰撞污染；
    2. IDF 降权：高频泛词（数字、通用英文词）自动获得接近 0 的权重，天然抗噪；
    3. Sublinear TF：抑制长切片中重复词条的分数膨胀，长文本检索更稳。

    稀疏表示（2026-09-20 演进）：向量仅保留非零项 {词表下标: L2 归一化权重}，
    单条切片约 2~4KB（稠密定长 8192 维 JSON 约 72KB），且词表扩容不再改变向量体积。
    TfidfVectorizer 默认 norm='l2'，transform 输出即归一化权重，直接取非零项即可。

    校准结论（在 3 篇真实博文 / 18 个切片上实测）：
    - 相关查询：31% ~ 51%（QLoRA 量化 49.3%，自注意力缩放因子 40.8%）
    - 无关查询：1% ~ 8%（vue 8.9%，红烧肉 10.4%，java 垃圾回收 5.3%）
    - 两条完全无关文本：接近 0%

    局限（诚实说明）：这是词法相关度而非语义嵌入。"vue" 与 "LoRA" 本身无共同词元，
    分数必然很低，这正是期望行为；它无法理解同义词（「显存」vs「显存占用」可以，
    「视频内存」vs「显存」不行）。若要真正的语义召回，需接入 RemoteAPIEmbedder。
    """

    def __init__(self):
        # 语料词表由语料库拟合产生，初始状态为空（未拟合时只做词元提取）
        self._fitted = False
        self.vectorizer = self._build_vectorizer()
        # 服务启动时优先加载上一次「全量重建」持久化的词表，
        # 保证查询向量与库内向量处于同一向量空间（见 _VECTORIZER_PATH 注释）
        self._try_load_fitted()

    def _build_vectorizer(self) -> TfidfVectorizer:
        """按当前代码配置构造向量化器（超参数以本文件为准，绝不复用反序列化来的旧对象）"""
        return TfidfVectorizer(
            analyzer="word",
            tokenizer=_tokenize_text,
            preprocessor=None,
            lowercase=False,
            token_pattern=None,
            ngram_range=(1, 2),       # 词 + 相邻词对，增强「显存 优化」类短语匹配
            sublinear_tf=True,
            max_features=MAX_VOCAB_SIZE,  # 仅内存软上限；稀疏存储下不再裁剪向量长度
            dtype=np.float32,
        )

    def _try_load_fitted(self) -> None:
        """从磁盘加载已拟合的词表；文件缺失、损坏或超参与当前代码不符时保持未拟合状态"""
        if not _VECTORIZER_PATH.exists():
            return
        try:
            vectorizer = joblib.load(_VECTORIZER_PATH)
            if vectorizer is None or not hasattr(vectorizer, "idf_"):
                return
            # 超参一致性校验：持久化词表若由旧配置（如旧的 max_features）拟合而来，
            # 其维度语义与当前代码不一致，必须丢弃并由「全量重建」重新拟合。
            # 否则改了超参后跑重建，仍会在反序列化回来的旧对象上拟合，新配置永远不生效。
            if getattr(vectorizer, "max_features", None) != MAX_VOCAB_SIZE:
                logger.warning(
                    f"持久化词表的 max_features={getattr(vectorizer, 'max_features', None)} "
                    f"与当前配置 {MAX_VOCAB_SIZE} 不一致，已丢弃，请执行全量重建"
                )
                return
            self.vectorizer = vectorizer
            self._fitted = True
            logger.info(f"已加载持久化 TF-IDF 词表 ({len(vectorizer.vocabulary_)} 词条)")
        except Exception as e:
            logger.warning(f"加载持久化 TF-IDF 词表失败，将退回即时拟合: {e}")

    def _persist(self) -> None:
        """拟合完成后将词表/IDF 落盘，保证服务重启后检索向量空间不漂移"""
        try:
            joblib.dump(self.vectorizer, _VECTORIZER_PATH)
            logger.info(f"TF-IDF 词表已持久化至 {_VECTORIZER_PATH.name} ({len(self.vectorizer.vocabulary_)} 词条)")
        except Exception as e:
            logger.warning(f"持久化 TF-IDF 词表失败，服务重启后需重新执行全量重建: {e}")

    def fit_corpus(self, texts: Iterable[str]) -> "LocalSemanticEmbedder":
        """用语料库拟合 IDF 词表（索引重建时调用一次即可），并持久化到磁盘"""
        corpus = [t for t in texts if t]
        if not corpus:
            return self
        # 始终按当前代码配置重建向量化器后再拟合：
        # 若复用启动时反序列化回来的旧对象，其 max_features 等超参会继续生效，
        # 导致「改了配置却重建不出新词表」的静默失效。
        self.vectorizer = self._build_vectorizer()
        self.vectorizer.fit(corpus)
        self._fitted = True
        self._persist()
        return self

    def embed_sparse_batch(self, texts: Iterable[str]) -> List[Dict[int, float]]:
        """
        批量编码：TF-IDF 加权（transform 输出已按行 L2 归一化），返回非零项稀疏向量。
        未登录词/符号可能触发 transform 报错，统一容错为全零（空稀疏向量）。
        """
        texts = [t if t else "" for t in texts]
        if not texts:
            return []

        if not self._fitted:
            # 未拟合时退化：语料过小，直接逐条拟合，保证仍可编码
            self.fit_corpus(texts)

        # 未登录词/符号可能触发 transform 报错，统一容错
        try:
            matrix = self.vectorizer.transform(texts)  # CSR，行已 L2 归一化
        except ValueError:
            matrix = sp.csr_matrix((len(texts), 1), dtype=np.float32)

        matrix = matrix.tocsr()
        vectors: List[Dict[int, float]] = []
        for row_idx in range(matrix.shape[0]):
            row = matrix.getrow(row_idx)
            vectors.append({
                int(col): round(float(val), 6)
                for col, val in zip(row.indices, row.data)
                if val > 0
            })
        return vectors

    def embed_sparse(self, text: str) -> Dict[int, float]:
        """将任意文本编码为稀疏 TF-IDF 向量 {词表下标: L2 归一化权重}"""
        return self.embed_sparse_batch([text])[0]

    def analyze_informativeness(self, text: str) -> Dict[str, List[str]]:
        """
        查询词元的信息量分析：把分词结果按「是否携带主题信息」分为三类。

        - informative_known: 主题词且已登录语料词表（知识库可检索到该主题）；
        - informative_oov:   主题词但未登录词表 —— 语料完全没有覆盖的主题信号，
          这是判定离题查询（如「红烧肉怎么做」中的「红烧肉」）的关键证据；
        - filler:            通用高频框架词（怎么做/什么/想/实现等），不携带主题信息，
          即使它们命中了语料词表甚至贡献了覆盖率，也不能证明主题相关。

        必须在词表拟合后调用（未拟合时词表无法反映语料主题覆盖面）。
        """
        if not self._fitted:
            raise RuntimeError("TF-IDF 词表未拟合，无法进行词元信息量分析")
        # jieba 词典惰性加载：在首次分词前 FREQ 为空，必须先确保初始化
        jieba.initialize()
        vocab = self.vectorizer.vocabulary_
        result: Dict[str, List[str]] = {
            "informative_known": [],
            "informative_oov": [],
            "filler": [],
        }
        for token in _tokenize_text(text):
            freq = jieba.dt.FREQ.get(token)
            if freq is not None and freq >= _FREQ_FILLER_MIN:
                result["filler"].append(token)
            elif token in vocab:
                result["informative_known"].append(token)
            else:
                result["informative_oov"].append(token)
        return result


class RemoteAPIEmbedder:
    """基于官方 OpenAI SDK 的远程商业向量接口适配器 (如 text-embedding-3-small, 智谱 embedding-3 等)"""
    def __init__(self, api_key: str, base_url: str, model_name: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)

    async def embed_text(self, text: str) -> List[float]:
        """调用官方 OpenAI SDK 生成高维语义嵌入向量"""
        resp = await self.client.embeddings.create(
            model=self.model_name,
            input=text[:4000]
        )
        return resp.data[0].embedding


_local_embedder = LocalSemanticEmbedder()


def fit_embedding_corpus(texts: Iterable[str]) -> None:
    """
    用语料库全局拟合 TF-IDF 词表与 IDF 权重。

    必须在重建索引前对整个语料调用，否则 IDF 只反映单篇切片，权重会失真。
    """
    _local_embedder.fit_corpus(texts)


def get_sparse_embedding(text: str) -> Dict[int, float]:
    """
    统一查询向量获取门面方法：文本 -> 稀疏 TF-IDF 向量 {词表下标: 权重}

    查询专用入口：先剥离问句虚词再向量化（疑问代词/否定词在技术语料中稀有、
    IDF 虚高，会同时扭曲余弦分与覆盖率门控，详见 vector_store.QUERY_STOPWORDS）。
    索引侧请继续使用 embed_sparse / get_sparse_embeddings，保持语料向量不受影响。
    """
    from app.ai_engine.vector_store import strip_query_stopwords
    return _local_embedder.embed_sparse(strip_query_stopwords(text))


def get_sparse_embeddings(texts: Iterable[str]) -> List[Dict[int, float]]:
    """批量稀疏向量获取门面方法 (供全量重建索引时一次性矩阵变换提速)"""
    return _local_embedder.embed_sparse_batch(texts)


def analyze_query_informativeness(text: str) -> Dict[str, List[str]]:
    """
    查询词元信息量分析门面方法：区分主题词（已登录/未登录）与通用泛词。
    词表未拟合时抛出 RuntimeError，由调用方决定是否降级放行。
    """
    return _local_embedder.analyze_informativeness(text)
