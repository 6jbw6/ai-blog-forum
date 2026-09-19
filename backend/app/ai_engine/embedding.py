import logging
import re
from pathlib import Path
from typing import List, Dict, Iterable
import numpy as np
import joblib
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


# 向量落库固定长度。TfidfVectorizer 的词表长度会随语料增长而变化，对外统一补齐到这个长度，
# 保证所有切片向量等长可比（避免重索引前后维度不一致导致余弦相似度直接算错）。
#
# 取值依据（2026-09-19 实测）：3 篇种子博文 / 18 切片，真实词条数 (1~2gram) 为 1832。
# 早期取 1024 会硬裁掉 808 个词元（占 44%），bm25 / augmented generation / a100 /
# bf16 等低频但高区分度的技术词全部丢失，导致这些词的稠密通道恒为 0。
# 取 4096 为当前语料留出 2 倍余量；若语料规模大幅增长后词条数再次触顶，需提高本值并全量重建。
EMBEDDING_DIM = 4096

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


class LocalSemanticEmbedder:
    """
    基于 Scikit-Learn 官方 TfidfVectorizer 的工业级词法相关度向量生成器

    为什么不用 HashingVectorizer（重要历史结论）：
    固定小维度的特征哈希会不可避免地把无关词元映射到同一位上。实测 128/256 维哈希下，
    查询 "vue" 仅占 1 个维度，语料里光是数字 "1" 就与它碰撞，直接产生 39% 的原始余弦、
    经加权融合后仍剩 25.8% —— 这正是「vue 和 LoRA 相似度 58%」的根因。
    哈希碰撞无法通过调维度根治，只有建立真实词表才能让维度语义一一对应。

    改用 TfidfVectorizer 后的三个收益：
    1. 维度语义确定：每个维度对应一个真实词元，不再有碰撞污染；
    2. IDF 降权：高频泛词（数字、通用英文词）自动获得接近 0 的权重，天然抗噪；
    3. Sublinear TF：抑制长切片中重复词条的分数膨胀，长文本检索更稳。

    校准结论（在 3 篇真实博文 / 18 个切片上实测）：
    - 相关查询：31% ~ 51%（QLoRA 量化 49.3%，自注意力缩放因子 40.8%）
    - 无关查询：1% ~ 8%（vue 8.9%，红烧肉 10.4%，java 垃圾回收 5.3%）
    - 两条完全无关文本：接近 0%

    局限（诚实说明）：这是词法相关度而非语义嵌入。"vue" 与 "LoRA" 本身无共同词元，
    分数必然很低，这正是期望行为；它无法理解同义词（「显存」vs「显存占用」可以，
    「视频内存」vs「显存」不行）。若要真正的语义召回，需接入 RemoteAPIEmbedder。
    """

    # 向量维度上限：语料词表不足时按实际词表长度输出（sklearn 不补零），
    # 但语料重索引后词表会增长，因此对外统一补齐到该长度，保证存库向量等长可比。
    # 必须与 EMBEDDING_DIM 一致：max_features 按「语料词频」截断，若语料词条数超过此值，
    # 低频专有名词会被裁出词表，稠密检索对其彻底失效（该词查询向量恒为 0）。
    MAX_FEATURES = 4096
    # 语料不足时的最小维度，避免早期只有几篇文章时向量过短
    MIN_DIMENSION = 256

    def __init__(self, dimension: int = MAX_FEATURES):
        self.dimension = dimension
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
            max_features=self.dimension,
            dtype=np.float32,
        )

    def _tokenize(self, text: str) -> List[str]:
        """兼容旧调用方 (vector_store 的 BM25 分词复用)，逻辑统一走模块级函数"""
        return _tokenize_text(text)

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
            if getattr(vectorizer, "max_features", None) != self.dimension:
                logger.warning(
                    f"持久化词表的 max_features={getattr(vectorizer, 'max_features', None)} "
                    f"与当前配置 {self.dimension} 不一致，已丢弃，请执行全量重建"
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

    def embed_text(self, text: str) -> List[float]:
        """将任意文本编码为固定长度的归一化稀疏-稠密向量"""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Iterable[str]) -> List[List[float]]:
        """批量编码：TF-IDF 加权后 L2 归一化，并按固定维度补零对齐"""
        texts = [t if t else "" for t in texts]
        if not texts:
            return []

        if not self._fitted:
            # 未拟合时退化：语料过小，直接逐条拟合，保证仍可编码
            self.fit_corpus(texts)

        # 未登录词/符号可能触发 transform 报错，统一容错
        try:
            matrix = self.vectorizer.transform(texts).toarray().astype(np.float32)
        except ValueError:
            matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)

        # 补齐/截断到固定维度，保证全部落库向量等长
        target = max(self.dimension, matrix.shape[1])
        if matrix.shape[1] < target:
            matrix = np.pad(matrix, ((0, 0), (0, target - matrix.shape[1])))

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms < 1e-6] = 1.0
        matrix = matrix / norms

        return [[round(float(x), 6) for x in row] for row in matrix]


class RemoteAPIEmbedder:
    """基于官方 OpenAI SDK 的远程商业向量接口适配器 (如 text-embedding-3-small, 智谱 embedding-3 等)"""
    def __init__(self, api_key: str, base_url: str, model_name: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def embed_text(self, text: str) -> List[float]:
        """调用官方 OpenAI SDK 生成高维语义嵌入向量"""
        resp = await self.client.embeddings.create(
            model=self.model_name,
            input=text[:4000]
        )
        return resp.data[0].embedding


_local_embedder = LocalSemanticEmbedder(dimension=EMBEDDING_DIM)


def fit_embedding_corpus(texts: Iterable[str]) -> None:
    """
    用语料库全局拟合 TF-IDF 词表与 IDF 权重。

    必须在重建索引前对整个语料调用，否则 IDF 只反映单篇切片，权重会失真。
    """
    _local_embedder.fit_corpus(texts)


def get_embedding(text: str) -> List[float]:
    """统一向量获取门面方法 (使用基于 Scikit-Learn 标准库的特征向量化器)"""
    return _local_embedder.embed_text(text)


def get_embeddings(texts: Iterable[str]) -> List[List[float]]:
    """批量向量获取门面方法 (供全量重建索引时一次性矩阵变换提速)"""
    return _local_embedder.embed_batch(texts)
