import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 将当前目录加入 python 搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.tag import Tag
from app.models.article import Article
from app.models.comment import Comment
from app.ai_engine.rag_service import rag_service


def seed_database():
    print("🚀 正在初始化数据库表结构...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. 初始化管理员账号
        admin = db.query(User).filter((User.username == "南柯") | (User.role == "admin")).first()
        if not admin:
            print("👤 创建初始管理员账号: 南柯")
            admin = User(
                username="南柯",
                password_hash=hash_password("jbw261932"),
                email="3768183086@qq.com",
                nickname="南柯",
                avatar="https://api.dicebear.com/7.x/bottts/svg?seed=admin",
                role="admin"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            print(f"👤 管理员账号 {admin.username} 已就绪。")

        # 2. 初始化标签（AI 技术标签库，博主写博时直接选择；管理后台可自行增删）
        tag_map = {}
        tags_data = [
            # —— 大模型与基础架构 ——
            {"name": "Transformer", "slug": "transformer", "color": "#E6A23C"},
            {"name": "LLM", "slug": "llm", "color": "#409EFF"},
            {"name": "深度学习", "slug": "deep-learning", "color": "#F59E0B"},
            {"name": "PyTorch", "slug": "pytorch", "color": "#EE4C2C"},
            {"name": "注意力机制", "slug": "attention", "color": "#D97706"},
            {"name": "MoE", "slug": "moe", "color": "#D946EF"},
            {"name": "多模态", "slug": "multimodal", "color": "#8B5CF6"},
            {"name": "长上下文", "slug": "long-context", "color": "#3B82F6"},
            # —— RAG 与知识库 ——
            {"name": "RAG知识库", "slug": "rag", "color": "#67C23A"},
            {"name": "向量检索", "slug": "vector-search", "color": "#10b981"},
            {"name": "向量数据库", "slug": "vector-database", "color": "#06B6D4"},
            {"name": "Embedding", "slug": "embedding", "color": "#14B8A6"},
            {"name": "Milvus", "slug": "milvus", "color": "#0EA5E9"},
            {"name": "FAISS", "slug": "faiss", "color": "#64748B"},
            {"name": "BM25", "slug": "bm25", "color": "#78716C"},
            {"name": "LangChain", "slug": "langchain", "color": "#22C55E"},
            {"name": "LlamaIndex", "slug": "llamaindex", "color": "#84CC16"},
            # —— Agent 与应用层 ——
            {"name": "AI Agent", "slug": "ai-agent", "color": "#7C3AED"},
            {"name": "Function Calling", "slug": "function-calling", "color": "#6366F1"},
            {"name": "MCP", "slug": "mcp", "color": "#0EA5E9"},
            {"name": "Prompt Engineering", "slug": "prompt-engineering", "color": "#E6A23C"},
            {"name": "LangGraph", "slug": "langgraph", "color": "#0891B2"},
            # —— 训练与微调 ——
            {"name": "LoRA微调", "slug": "lora", "color": "#F56C6C"},
            {"name": "QLoRA", "slug": "qlora", "color": "#F97316"},
            {"name": "微调", "slug": "fine-tuning", "color": "#FB7185"},
            {"name": "RLHF", "slug": "rlhf", "color": "#EC4899"},
            {"name": "知识蒸馏", "slug": "knowledge-distillation", "color": "#A855F7"},
            # —— 推理与部署 ——
            {"name": "模型量化", "slug": "quantization", "color": "#F59E0B"},
            {"name": "推理优化", "slug": "inference-optimization", "color": "#10B981"},
            {"name": "vLLM", "slug": "vllm", "color": "#EF4444"},
            # —— 工程侧 ——
            {"name": "FastAPI", "slug": "fastapi", "color": "#009688"},
            {"name": "Vue3", "slug": "vue3", "color": "#059669"},
            {"name": "计算机视觉", "slug": "computer-vision", "color": "#0284C7"},
        ]
        for tdata in tags_data:
            tag = db.query(Tag).filter(Tag.slug == tdata["slug"]).first()
            if not tag:
                tag = Tag(**tdata)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            tag_map[tdata["slug"]] = tag

        # 3. 插入核心高水准技术博文 (面试杀手锏)
        articles_data = [
            {
                "title": "深入浅出 Transformer 架构：自注意力机制推导与矩阵计算实现",
                "slug": "deep-dive-into-transformer-self-attention",
                "summary": "系统解析 Transformer 中的核心自注意力机制 (Self-Attention)，推导 Q、K、V 矩阵计算过程、Softmax 缩放因子的数学必要性以及多头注意力 (Multi-Head Attention) 的工程实现。",
                "tag_slugs": ["transformer", "vector-search"],
                "is_top": True,
                "views_count": 528,
                "likes_count": 64,
                "content": """# 深入浅出 Transformer 架构：自注意力机制推导与矩阵计算实现

自 2017 年 Google 提出 《Attention Is All You Need》 以来，Transformer 架构彻底颠覆了自然语言处理（NLP）与计算机视觉（CV）领域，成为当下大语言模型（LLM）如 GPT-4、DeepSeek、Llama 的基石。

本文将从数学直觉、公式推导与矩阵运算代码三个维度，彻底拆解其核心灵魂 —— **自注意力机制 (Self-Attention)**。

---

## 1. 为什么需要自注意力？

在 RNN/LSTM 时代，网络处理序列数据依赖时序递归传递隐藏状态 $h_t = f(h_{t-1}, x_t)$。这带来了两大致命痛点：
1. **难以捕获超长程依赖关系**：随着时间步增长，梯度消失/爆炸导致前期上下文信息衰减严重；
2. **无法并行计算**：每个时间步的计算严格依赖上一个时间步的输出，难以发挥 GPU 的超大算力集群优势。

自注意力机制通过全局任意两点之间的直接注意力交互，将长程依赖的信息交互路径长度缩短至 $O(1)$，并天然实现了全并行张量运算。

---

## 2. Q、K、V 矩阵的本质与数学映射

在自注意力计算中，每个输入词向量 $x_i$ 都会被线性投影为三个不同的向量：
- **Query (查询向量 $Q$)**：代表“我在寻找什么信息”；
- **Key (键向量 $K$)**：代表“我拥有什么特征可以被匹配”；
- **Value (值向量 $V$)**：代表“我实际承载的内容是什么”。

设输入特征矩阵为 $X \\in \\mathbb{R}^{N \\times d_{model}}$，通过三个可学习的线性权重矩阵变换：
$$Q = X W_Q, \\quad K = X W_K, \\quad V = X W_V$$

---

## 3. 核心计算公式与缩放因子的意义

点积注意力的经典公式如下：
$$\\text{Attention}(Q, K, V) = \\text{Softmax}\\left(\\frac{Q K^T}{\\sqrt{d_k}}\\right) V$$

### 核心考点：为什么必须除以 $\\sqrt{d_k}$？
假设 $Q$ 和 $K$ 的各分量是均值为 0、方差为 1 的独立同分布随机变量。其内积：
$$q \\cdot k = \\sum_{i=1}^{d_k} q_i k_i$$
该内积的和服从均值为 0，方差为 $d_k$ 的分布。当维度 $d_k$ 很大时（例如 64 或 128），内积的绝对值会变得极大。

若直接送入 Softmax 函数，极端值会导致输出概率分布严重向最大值偏移，此时 **Softmax 的导数极小（进入饱和区）**，反向传播时将出现严重的 **梯度消失 (Gradient Vanishing)**。除以 $\\sqrt{d_k}$ 能将方差重新缩放回 1，保持数值平稳与平滑的梯度流。

---

## 4. 多头注意力机制 (Multi-Head Attention)

单一注意力头只能捕捉单一子空间的语义相似度。通过将特征切分为 $h$ 个头：
$$\\text{MultiHead}(Q, K, V) = \\text{Concat}(\\text{head}_1, \\dots, \\text{head}_h) W_O$$
模型能够在不同维度、不同语义偏好下同时关注句子的语法关系、实体指代与上下文语境。

在实际大模型应用与工程落地中，FlashAttention 通过切块矩阵乘法（Tiling）进一步减少了 HBM 与 SRAM 之间的高昂读写延迟，成为高吞吐量训练与推理的标配。
"""
            },
            {
                "title": "大模型轻量微调实战：从 LoRA 到 QLoRA 核心原理与显存优化",
                "slug": "llm-parameter-efficient-fine-tuning-lora-qlora",
                "summary": "针对大模型全量微调（Full Fine-Tuning）对 GPU 显存消耗巨大的痛点，深度剖析低秩自适应 (LoRA) 与量化 LoRA (QLoRA) 的数学原理、本征秩假设以及工程落地显存估算。",
                "tag_slugs": ["lora", "transformer", "fastapi"],
                "is_top": False,
                "views_count": 412,
                "likes_count": 48,
                "content": """# 大模型轻量微调实战：从 LoRA 到 QLoRA 核心原理与显存优化

对于绝大多数算法工程师与企业落地团队而言，全量微调（Full Parameter Fine-Tuning）70B 甚至 7B 的大语言模型成本极其高昂。例如，对 7B 浮点参数（FP16/BF16）进行全参数微调，加上优化器状态（AdamW 需存储一阶动量和二阶方差，占 12 字节/参数）、梯度和激活值，至少需要 80GB+ 显存（如 A100/H100 显卡）。

**参数高效微调 (PEFT, Parameter-Efficient Fine-Tuning)** 应运而生，其中最经典的代表便是 **LoRA (Low-Rank Adaptation)** 和 **QLoRA**。

---

## 1. LoRA 的本征秩假说 (Intrinsic Rank Hypothesis)

微软团队在 2021 年提出 LoRA 时基于一个深刻洞见：
> 预训练大模型在特定下游任务上微调时，权重的实际更新量 $\\Delta W$ 具有很低的“本征秩 (Intrinsic Rank)”。

换言之，并不需要改变原始权重的所有自由度，极少数量的主成分自由度即可拟合下游任务的特征分布。

---

## 2. 数学公式与结构拆解

对于预训练权重矩阵 $W_0 \\in \\mathbb{R}^{d \\times k}$，LoRA 将其参数更新矩阵分解为两个极低秩矩阵的乘积：
$$W = W_0 + \\Delta W = W_0 + \\frac{\\alpha}{r} (B \\times A)$$
- 其中 $A \\in \\mathbb{R}^{r \\times k}$ 采用高斯随机分布初始化；
- $B \\in \\mathbb{R}^{d \\times r}$ 初始置为 0，确保训练之初 $\\Delta W = 0$；
- 秩 $r \\ll \\min(d, k)$（通常取 8, 16 或 32）；
- $\\alpha$ 为缩放常数（超参数），用于调节 LoRA 权重对原始模型的影响幅度。

在反向传播时，原始权重 $W_0$ 被彻底冻结（不计算梯度，无需存储优化器状态），仅计算并更新极小规模的 $A$ 与 $B$，可训练参数量直接下降 99% 以上！

### 核心亮点：零推理延迟
在训练完成部署上线时，由于矩阵加法满足结合律：
$$W_{deploy} = W_0 + \\frac{\\alpha}{r} BA$$
可以在服务启动前将参数直接无损合并回原始权重，在生产推理阶段产生 **零额外延迟 (Zero Inference Overhead)**。

---

## 3. QLoRA 的三大工程革命

华盛顿大学提出的 QLoRA 将微调门槛降低到了极致，单张消费级显卡（如 RTX 3090/4090 24GB）即可微调 65B 参数大模型：
1. **NF4 (NormalFloat 4) 量化**：专为正态分布权重设计的信息论最优 4 位量化数据类型；
2. **双重量化 (Double Quantization)**：对量化常数再次进行量化，平均每个参数再节省 0.37 bit 显存；
3. **分页优化器 (Paged Optimizers)**：利用 CUDA Unified Memory 机制，在长序列激活值显存峰值突发时，自动将优化器状态页移至 CPU 内存，彻底防止 OOM (Out Of Memory)。
"""
            },
            {
                "title": "基于 RAG 架构的企业级知识库问答系统落地实践与多路召回调优",
                "slug": "enterprise-rag-system-architecture-hybrid-retrieval",
                "summary": "从工程实战角度阐述构建高精度 RAG 系统的全生命周期：Markdown 标题感知递归切块、向量稠密检索与关键词稀疏检索的多路召回策略、防幻觉 System Prompt 与 SSE 流式输出。",
                "tag_slugs": ["rag", "vector-search", "fastapi", "vue3"],
                "is_top": True,
                "views_count": 689,
                "likes_count": 89,
                "content": """# 基于 RAG 架构的企业级知识库问答系统落地实践与多路召回调优

大语言模型（LLM）虽然具备强大的通识推理能力，但在企业私有领域面临着两大致命短板：
1. **时效性滞后与私域数据黑盒**：预训练知识截止于训练时间点，且无法直接读取企业内网文档或个人博文；
2. **不可控的“大模型幻觉 (Hallucination)”**：遇到未知问题时容易煞有介事地一本正经胡说八道。

**检索增强生成 (RAG, Retrieval-Augmented Generation)** 通过在生成阶段动态检索私有知识库并将其实时注入 Prompt 上下文，成为目前行业落地的首选架构。

---

## 1. RAG 核心三步流与架构全景

完整的 RAG 生命周期分为四个核心阶段：
1. **文档摄取 (Ingestion)**：数据清洗、Markdown 标题感知切块与向量嵌入 (Embedding)；
2. **检索对齐 (Retrieval)**：根据读者 Query，在向量空间中召回相关度最高的切片；
3. **上下文增强 (Augmentation)**：组装系统提示词、知识引用约束与来源溯源元数据；
4. **生成交付 (Generation)**：调用大模型通过 SSE (Server-Sent Events) 打字机流式输出给读者。

---

## 2. 切块策略 (Chunking Strategy)：决定 RAG 上限的暗箱

许多初学者直接按固定字符数（如 500 字一刀切），这往往会导致：
- 句子被拦腰截断，关键主谓宾语义丢失；
- 丢失章节层级归属（读者提问某个二级标题下的问题，切片中却无标题上下文）。

### 本项目的解决方案：标题感知递归分块 (Title-Aware Recursive Chunker)
1. 识别 Markdown `#`, `##`, `###` 标题，将当前切片前置拼接章节路径（如 `【章节: 自注意力机制计算】`）；
2. 保持段落和标点符号完整，设置滑动窗口重叠步长（Overlap: 60 字符），保证跨边界语义的连贯性。

---

## 3. 多路召回 (Hybrid Retrieval) 为什么远胜纯向量检索？

纯 Dense Embedding 检索擅长捕获语义泛化（例如搜“显存不够”能召回“LoRA量化减小显存”），但在面对以下场景时容易失效：
- **专有名词 / 缩写**：如 API 方法名 `cosine_similarity`、错误码 `HTTP 422`、特定人名；
- **数字精确匹配**：如 `Python 3.13`、`MySQL 8.0`。

为此，本项目引入 **多路召回与混合加权排序 (Hybrid Dense-Sparse Reranking)**：
$$\\text{Final Score} = \\alpha \\cdot \\text{Sim}_{dense} + (1 - \\alpha) \\cdot \\text{Score}_{sparse}$$
- $\\text{Sim}_{dense}$：词法特征向量（维度上限 4096）的余弦相似度（权重 0.75）；
- $\\text{Score}_{sparse}$：分词/BM25 词频匹配命中率（权重 0.25）。

实验证明，混合检索模式能使 Top-3 召回命中率提升 25% 以上。

---

## 4. 全链路 SSE 流式打字机交互与知识溯源直达

为了给读者极致的用户交互体验，后端采用 FastAPI 异步生成器 (`yield token`) 配合 `text/event-stream` 协议输出：
- 前端通过 Fetch API 读取 ReadableStream，实时渲染打字机动画；
- 在生成完毕时，系统附带推送引用的博文段落卡片，读者点击即可一键锚点跳转至对应文章，从根源上消除了大模型幻觉，建立强信任感。
"""
            }
        ]

        for art_data in articles_data:
            existing = db.query(Article).filter(Article.slug == art_data["slug"]).first()
            if not existing:
                print(f"📝 写入技术博文: 《{art_data['title']}》")
                tags = [tag_map[tslug] for tslug in art_data["tag_slugs"]]
                art = Article(
                    title=art_data["title"],
                    slug=art_data["slug"],
                    summary=art_data["summary"],
                    content=art_data["content"],
                    is_published=True,
                    is_top=art_data["is_top"],
                    views_count=art_data["views_count"],
                    likes_count=art_data["likes_count"],
                    author_id=admin.id,
                    tags=tags
                )
                db.add(art)
                db.commit()
                db.refresh(art)

                # 自动为文章执行向量化分块构建 RAG 知识库
                chunk_count = rag_service.index_article(db, art.id)
                print(f"   ⚡ 成功切分并建立 {chunk_count} 个向量切片索引！")
            else:
                print(f"📝 博文 《{art_data['title']}》 已存在，跳过。")

        # 4. 添加示例评论
        sample_article = db.query(Article).first()
        if sample_article:
            c_count = db.query(Comment).filter(Comment.article_id == sample_article.id).count()
            if c_count == 0:
                print("💬 添加初始读者评论互动...")
                root_comment = Comment(
                    article_id=sample_article.id,
                    user_name="李明 (算法硕博在读)",
                    user_email="liming@edu.cn",
                    user_avatar="https://api.dicebear.com/7.x/bottts/svg?seed=liming",
                    content="博主推导得很清晰！特别是指出了除以 sqrt(d_k) 防止梯度消失的细节，校招面试时被一线大厂面试官问到过这个点！",
                    is_approved=True,
                    is_admin=False
                )
                db.add(root_comment)
                db.commit()
                db.refresh(root_comment)

                reply_comment = Comment(
                    article_id=sample_article.id,
                    parent_id=root_comment.id,
                    user_name="博主",
                    user_email="admin@aiblog.com",
                    user_avatar=admin.avatar,
                    content="感谢认可！这个问题在深入推导 Softmax 雅可比矩阵的时候非常直观，欢迎多交流！也可以随时在右下角和我配置的 AI 智能体聊聊其他算法细节~",
                    is_approved=True,
                    is_admin=True
                )
                db.add(reply_comment)
                db.commit()

        print("✅ 数据库表结构、初始数据与 RAG 向量知识库初始化圆满完成！")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
