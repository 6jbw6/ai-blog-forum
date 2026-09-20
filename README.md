# AI博客论坛 — 基于 RAG 与大模型协同的企业级博客论坛系统

> 一个面向 **AI 算法 / 大模型应用开发（RAG · Agent · LLM Application）** 方向的企业级全栈实战项目：
> 以博客论坛为业务载体，完整落地了一条工业级 RAG 链路 —— 标题感知切块 → TF-IDF 向量化 → 多路召回混合重排 → SSE 流式生成 → 知识溯源引用。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2.0 · Pydantic V2 · MySQL 8.0 |
| AI 引擎 | LangChain Text Splitters · Scikit-Learn (TfidfVectorizer) · Rank-BM25 · Jieba · OpenAI SDK (AsyncOpenAI) |
| 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia · Axios |
| 内容渲染 | Markdown · KaTeX · highlight.js |
| 鉴权 | JWT (PyJWT) · Bcrypt 密码加盐 · 前端全局路由守卫 |

---

## 核心功能

### 1. RAG 知识库问答（SSE 流式 + 溯源引用）
- `POST /api/v1/ai/ask` 全链路 SSE 打字机流式输出，首 Token 低延迟；
- 回答末尾推送结构化「知识来源卡片」，同一篇文章只保留相关度最高切片，跨文章取 Top-3，点击直达原文；
- 多轮对话上下文、按账号隔离的对话历史持久化（`ai_chat_messages`）与自动恢复；
- 防幻觉 System Prompt：知识库有据可依、超纲问题坦诚说明、禁止编造。

### 2. 语义检索（稀疏索引 + 多路召回 + 文章级主题判定）
- `POST /api/v1/ai/semantic-search`：自然语言检索博文，突破 LIKE 字面匹配局限；
- **进程级稀疏检索索引**（`retrieval_index.py`）：切片 TF-IDF 稀疏向量预拼装为 CSC 倒排矩阵，稠密余弦 / 查询覆盖率 / BM25 三路打分只遍历查询词元命中的倒排链，词表版本指纹节流探测 + 后台单飞重建，检索态常驻内存、请求线程零重建；
- 混合加权评分：`similarity = 0.75 × TF-IDF 余弦 + 0.25 × BM25 饱和映射 score/(score+8)`，再乘标题命中加成（查询词命中标题最高 ×1.25）；
- **查询侧虚词过滤**：疑问代词 / 否定词 / 语气词（如何、不够、什么…）在技术语料中稀有、IDF 虚高，会同时扭曲余弦与覆盖率，检索前统一剥离（语料侧分词与落库向量不受影响）；
- 召回门控以「查询词元覆盖率」为主判据（详见下文），`RAG_SIMILARITY_THRESHOLD=0.18` 作为辅助通道，可在管理后台「AI 设置」热调；
- **搜索单位是文章**：切片按文章去重聚合，文章级主题判定（命中切片数 ≥ 2 / 标题摘要概念命中 / 最佳分达标）剔除「仅正文顺带提及」的结果；
- 实测：主题查询（含自然语言问句）精准召回且按相关度排序，纯虚词与零重叠查询全部拒绝。

### 3. 动态推荐引擎
- `search_logs` 全链路热度埋点（AI 提问 / 语义搜索 / 门户搜索），闲聊问句黑名单防污染；
- 推荐问题与热搜概念由「真实搜索热度 + 高热博文衍生 + 兜底题库」多维融合，支持「换一批」。

### 4. 博客论坛社区
- 去中心化多作者：登录用户皆可发布 / 编辑 / 删除本人博文；
- **公开个人主页** `/user/:id`：头像 / 昵称 / 签名 / 获赞数 / 邮箱，Tabs 含博文（访客仅见已发布，本人另见未发布草稿并带「未发布 · 私有」标识）、评论、收藏、点赞、消息提醒；
- **用户搜索**：语义搜索结果中的「用户」维度，按用户名 / 昵称模糊匹配并附带博文数；
- **门户写作页** `/write`（登录即可写，不进后台）：Markdown 编辑 + 实时预览，支持「保存（未发布草稿）」与「发布（按公开发布开关落库为公开 / 私有）」，未发布文章带「未发布 · 私有」标识、详情页可见且仅作者可编辑；
- 点赞、收藏、评论（树形嵌套）、回复自动派发站内通知与未读红点；
- `search_hits` 热度驱动实时置顶：检索命中最多的前 3 篇博文自动加冕置顶（仅管理员可手动置顶）；
- 内置 33 个 AI 技术标签库（Transformer / LLM / RAG / Agent / LoRA / 推理优化…），写博时直接选择，管理后台可增删；
- KaTeX 数学公式渲染（含裸露 LaTeX / ASCII 伪代码容错转译）。

### 5. 管理后台
- 运营数据大屏、文章 / 分类 / 标签管理；
- 「AI 设置」：在线热切换大模型接入商（DeepSeek / 智谱 / OpenAI 或任意 OpenAI 兼容端点），`POST /api/v1/ai/models` 实时拉取可用模型列表，配置回写 `.env`；
- 「一键全量重建」RAG 向量知识库。

---

## RAG 引擎内部机制（重要）

代码位于 `backend/app/ai_engine/`，检索链路：`chunking.py → embedding.py → retrieval_index.py（进程级稀疏索引）→ vector_store.py → rag_service.py`。

1. **切块**（`chunking.py`）：LangChain `MarkdownHeaderTextSplitter` 按 H1～H4 构建章节面包屑，`RecursiveCharacterTextSplitter`（450 字符 / 60 重叠）保持段落完整，切片内容前置章节路径。
2. **向量化**（`embedding.py`）：Scikit-Learn `TfidfVectorizer`（Jieba 中英分词 + 停用词过滤 + 词/词对 bigram + sublinear TF）输出 L2 归一化稀疏向量，维度上限 4096（`EMBEDDING_DIM`）；查询入口 `get_sparse_embedding` 会先剥离问句虚词（见 `vector_store.QUERY_STOPWORDS`）。
   > 维度上限必须 ≥ 语料真实词条数：`max_features` 按词频硬裁，早期取 1024 时裁掉了 1832 个词条中的 808 个（44%），`bm25`、`a100`、`bf16` 等低频高区分度技术词全部丢失，导致这些词的稠密通道恒为 0。改维度后**必须全量重建**。
   > 说明：这是**词法相关度**而非语义嵌入。早期版本用 128 维 `HashingVectorizer`，因特征哈希碰撞导致无关文本相似度虚高（"vue vs LoRA 58%"），已废弃。需要真正语义召回时可启用预留的 `RemoteAPIEmbedder`（OpenAI 兼容嵌入接口）。
3. **词表持久化**（关键机制）：TF-IDF 词表 / IDF 是全局统计量。全量重建时 `fit_corpus()` 会把拟合好的词表落盘到 `app/ai_engine/tfidf_vectorizer.joblib`，服务启动时自动加载。
   > 若无此机制：服务重启后词表丢失，查询向量只能"拿查询词自己拟合"，与库内向量的维度语义完全错位，相关查询召回为 0。
4. **进程级稀疏检索索引**（`retrieval_index.py`）：切片稀疏向量预拼装为 CSC 倒排矩阵 + 自研 `Bm25Index`（CSC 倒排，与 rank_bm25 逐元素等价），以「切片总数 / 最大切片 ID / 发布文章数」轻量指纹节流探测变更、后台单飞重建、快照只读原子替换；请求线程零重建，实测万级切片单次检索毫秒级。
5. **检索打分**（`vector_store.py` + `IndexSnapshot.search`）：稠密余弦（权重 0.75）+ BM25 稀疏（权重 0.25）融合，查询虚词剥离、标题命中加成，按文章去重并做文章级主题判定。

### 召回门控：为什么不用「绝对分数阈值」

余弦相似度会同时被**查询长度**和**切片长度**摊薄：切片是 450 字长文本（数百个非零维度），
查询只有 1～2 个词元时，分母把分数压到 0.11～0.14；3 词以上查询可达 0.24～0.40。
因此**同一个绝对阈值无法同时适配长短查询**——卡 0.18 会滤掉 "RAG" 的正确结果，放宽又会放进噪声。
（曾尝试「按查询长度打折阈值」，实测暴露非单调缺陷：`RAG` 0.1102 过 0.108 放行，
更具体的 `RAG 知识库` 分数更高 0.1372 却因阈值跳到 0.153 被拒——查询变长反而搜不到，已废弃。）

现方案以**查询词元覆盖率**为主判据（`dense_and_coverage_scores`，一次倒排链遍历同时产出余弦与覆盖率）：
查询向量在切片中被命中的 TF-IDF 加权比例。它是「比例」量，分子分母同时随长度缩放，
天然与切片长度、查询长度无关，且直接复用已有向量、无需重新分词。

- 判据：`覆盖率 ≥ 0.5` **或** `融合分 ≥ RAG_SIMILARITY_THRESHOLD`，再统一过 `0.03` 数值噪声兜底；
- **查询侧虚词过滤**（`QUERY_STOPWORDS`）：自然语言问句里的「如何 / 不够 / 什么」等虚词在技术语料中稀有、IDF 虚高，
  会把覆盖率分母撑大——真实主题文章被误拒、恰好引用了问句短语的文章被误放行，检索前统一剥离（过滤后为空则原样返回）；
- **标题命中加成**：查询实义词命中文章标题时 `final × (1 + 0.25 × 命中比例)`，仅影响排序与展示分，不动门控判据；
- **展示的 `similarity` 与排序分一致**（含标题加成），不做任何拉伸或归一化，避免重蹈「Min-Max 把 Top-1 强行拉满」的覆辙。

### 已知局限

- **语料里没写过的词搜不到**：例如语料通篇用 LoRA/QLoRA，从未出现「低秩自适应」，该查询只能靠分词残片弱匹配。这是词法检索的固有边界，不是缺陷。
- **主题与提及需要语义区分**：文章级主题判定已大幅缓解（剔除仅正文顺带提及的结果），但纯词法模型无法真正理解语义，需要更高质量的主题区分则必须接入语义嵌入。
- 小语料下 IDF 的语义是「能区分文档」而非「重要」：主题词（如 `rag`）因高频出现 IDF 反而偏低，稀有词（`前端`、`路由`）IDF 偏高，因此 BM25 分量不能单独作为相关性判据。

### 运维须知
- **新增 / 修改博文**：保存时自动增量重建该文章的切片索引；
- **改动 embedding / 分词 / 切块逻辑后**：必须执行「管理后台 → 一键全量重建」（或调用 `rag_service.reindex_all_articles(db)`），因为 TF-IDF 需要先拟合全局词表，且新旧向量空间不一致会导致相似度计算错误；
- **改动 AI 引擎代码后必须重启后端**：`run.py` 以 `reload=False` 运行，旧进程不会加载新代码（曾因此出现"旧进程 256 维哈希查询向量 vs 库内 TF-IDF 向量"的维度不匹配 500 错误）。

---

## 目录结构

```
ai-blog-forum/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # RESTful 路由: auth / articles / comments / favorites
│   │   │                        #   notifications / ai_assistant / users / statistics ...
│   │   ├── api/deps.py          # JWT 鉴权与当前用户依赖注入
│   │   ├── core/                # config(Pydantic Settings) / database / security / response(统一封包+全局异常)
│   │   ├── models/              # ORM: user / article / article_chunk / search_log / ai_chat_message ...
│   │   ├── schemas/             # Pydantic DTO 契约
│   │   └── ai_engine/           # chunking / embedding / retrieval_index(进程级稀疏索引)
│   │                            #   vector_store / rag_service / llm_client / recommendation_service
│   │                            #   tfidf_vectorizer.joblib (持久化词表, 重建时自动生成)
│   ├── seed_data.py             # 建表 + 管理员 + 种子博文 + 向量知识库初始化
│   ├── requirements.txt
│   ├── run.py                   # 后端启动入口 (uvicorn)
│   └── .env                     # 本地环境配置 (不入库)
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios 请求封装
│   │   ├── components/          # Navbar / AiChatDrawer / MarkdownViewer / 用户弹窗 ...
│   │   ├── views/               # portal(门户: 首页/详情/搜索/个人主页/写作) / admin(后台) / auth(登录注册)
│   │   ├── router/              # 路由 + 全局登录守卫
│   │   └── stores/              # Pinia
│   └── package.json
└── .gitignore
```

---

## 快速启动

### 0. 环境准备
- Python 3.12+、Node.js 18+、MySQL 8.0（创建数据库 `ai_blog`，编码 `utf8mb4_unicode_ci`）

```powershell
# 后端依赖
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 前端依赖
cd ..\frontend
npm install
```

- 复制 `backend/.env.example` 为 `backend/.env`，填写数据库连接与 `LLM_API_KEY`；
- 首次运行执行播种脚本（建表 + 初始管理员「南柯」+ 种子博文 + 向量索引）：

```powershell
cd backend
.\venv\Scripts\python.exe seed_data.py
```

### 1. 启动后端
```powershell
cd backend
.\venv\Scripts\python.exe run.py
```
- API 服务：`http://127.0.0.1:8000`
- Swagger 文档：`http://127.0.0.1:8000/docs`

### 2. 启动前端
```powershell
cd frontend
npm run dev
```
- 门户地址：`http://localhost:5173`（浏览对游客开放；写作、评论、收藏等需登录）
- 初始管理员「南柯」，密码见 `seed_data.py`（建议首次登录后立即修改）

---

## 环境变量（backend/.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接 | 127.0.0.1:3306 / root / ai_blog |
| `LLM_PROVIDER` | 大模型接入商标识 | deepseek |
| `LLM_API_KEY` | 大模型密钥（也可在管理后台热配置） | - |
| `LLM_BASE_URL` | OpenAI 兼容端点 | https://api.deepseek.com |
| `LLM_MODEL` | 模型 ID | deepseek-chat |
| `RAG_TOP_K` | 问答注入上下文的切片数 | 4 |
| `RAG_SIMILARITY_THRESHOLD` | 检索相似度阈值 | 0.18 |

> 注意：`pydantic-settings` 按启动时的工作目录读取 `.env`，请务必在 `backend/` 目录下启动 `run.py`（脚本内已自动 chdir）。

---

## 主要 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/ai/ask` | RAG 知识库问答（SSE 流式 + 引用卡片） |
| POST | `/api/v1/ai/semantic-search` | 语义检索博文（文章级主题判定） |
| GET | `/api/v1/ai/recommended-questions` | 动态推荐问题（支持换一批） |
| GET | `/api/v1/ai/hot-keywords` | 动态热搜概念 |
| GET/DELETE | `/api/v1/ai/history` | 拉取 / 清空当前账号 AI 对话历史 |
| POST | `/api/v1/ai/reindex-all` | 全量重建向量知识库（管理员） |
| GET/PUT | `/api/v1/ai/config` | 读取 / 热更新大模型与 RAG 配置（管理员） |
| POST | `/api/v1/ai/models` | 在线拉取供应商可用模型列表（管理员） |
| GET | `/api/v1/articles` | 文章分页列表（关键词 / 标签 / 作者筛选；未发布仅作者本人与管理员可见） |
| GET | `/api/v1/users/search` | 按用户名 / 昵称模糊搜索用户（公开） |
| GET | `/api/v1/users/{id}/profile` | 用户公开资料（个人主页头部） |
| GET | `/api/v1/comments/my` | 当前用户评论时间线（需登录） |
| * | `/api/v1/auth/*` `/api/v1/comments/*` `/api/v1/favorites/*` `/api/v1/notifications/*` | 鉴权 / 评论 / 收藏 / 通知 |

---

## 常见问题排查

| 现象 | 根因与处理 |
|---|---|
| 语义搜索 / AI 问答返回 500「服务器内部错误」 | 多为**后端进程未重启**：AI 引擎代码改动后旧进程仍在内存中运行旧逻辑，与库内向量维度不匹配。重启后端即可。全局异常拦截器会吞掉真实堆栈，需看后端控制台日志定位。 |
| 重启后相关查询召回为 0 / 相似度异常 | 词表文件 `tfidf_vectorizer.joblib` 缺失或与库内向量不匹配。执行「一键全量重建」重新拟合 + 持久化。 |
| 修改 `.env` 后配置未生效 | `.env` 仅在进程启动时读取；或使用了管理后台热配置（其优先回写 `.env` 并热生效）。修改后请重启后端。 |
