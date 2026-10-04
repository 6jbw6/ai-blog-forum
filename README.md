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

### 4. 门户搜索体验（顶部胶囊搜索栏）
- **热搜词实时映射 placeholder**：空输入时每 3.5s 轮换一条真实热搜词（只取长度 ≤ 10 的短词、最多 6 条），回车或点「搜索」即搜当前展示词 —— 输入框永远有内容，**从根上杜绝空搜索**；
- `Ctrl + K` 全局聚焦搜索框；聚焦即展开下拉面板 =「搜索记录」+「热搜」chips 两段；
- **搜索记录 localStorage 持久化**（`search_history`）：超出预览条数自动折叠为「展开全部 (N) / 收起」，支持单条删除与一键清空，跨会话保留；
- **搜索词回显**：由 `/search?q=` 直达或刷新时把查询词自动填回搜索框，「搜过的词不丢」；
- 门户搜索走 `/api/v1/articles?keyword=`，同一关键词写入 `search_logs` 并实时累加命中博文的 `search_hits`，直接驱动上面 §3 的热度推荐与自动置顶。

### 5. 博客论坛社区
- 去中心化多作者：登录用户皆可发布 / 编辑 / 删除本人博文；
- **公开个人主页** `/user/:id`：头像 / 昵称 / 签名 / 获赞数 / 邮箱，Tabs 含博文（访客仅见已发布，本人另见未发布草稿并带「未发布 · 私有」标识）、评论、收藏、点赞、消息提醒；
- **个人资料自助修改**（顶栏头像下拉 → 个人资料）：用户名 / 昵称 / 签名 / 头像 / 密码，以及**电子邮箱**——邮箱走「主流服务商白名单」（QQ、163、126、Gmail、Outlook、iCloud、Yahoo、Zoho、阿里云、139 等），**不接受自有域名 / 自建邮局地址**，清单同时维护在前后端两处；修改时校验占用（忽略大小写），改完即可用新邮箱登录；站点主人（`role=admin`）在主页与评论区显示「站长」标识；
- **用户搜索**：语义搜索结果中的「用户」维度，按用户名 / 昵称模糊匹配并附带博文数；
- **写作页**（登录即可写）：Markdown 编辑 + 实时预览，可见性三态——未发布草稿、已发布但仅自己可见（`is_private`）、已发布公开；前两者对首页 / 标签页 / 用户搜索 / 语义检索 / RAG 知识库全部隐身，访客按 slug 直取同样 404，仅作者本人与管理后台可见。门户走 `/write` 与 `/write/:id`，管理后台侧栏「写作」走同一组件的内嵌路由 `/admin/write(/:id)`（保留左侧菜单，保存后回文章列表），文章详情页的编辑入口仍跳门户路径；
- 点赞、收藏、评论（无限层递归线程，每条可点赞 / 作者可改删 / 管理员可删，删除连带清理整条子线程）；
- **站内消息提醒**（`notifications`）：**回复你的评论** → 通知被回复者并附上被回复原文；**博文作者**始终收到博文下所有评论的提醒（含发生在别人评论线程里的回复），不会漏掉任何一条讨论；自评 / 自回不给自己发消息，同一人同一评论只发一条。提醒以 `kind` 区分类型（`article_comment` / `reply`），以 `comment_id` 关联触发它的评论；
- **提醒随源头实时更新**：发送者昵称与头像按账号（`sender_id`）**实时解析**——对方改昵称、换头像后历史提醒立即跟着变，账号注销才回退到创建时的快照；编辑评论后提醒里的正文与被回复原文同步覆盖；重新编辑博文的标题 / 别名后《标题》与跳转别名同步，旧 slug 不留死链；**评论被删除时提醒保留**，仅把内容标记为「该评论已删除」（外键 `ON DELETE SET NULL`，互动记录不断链）。以上同步都不重置 `is_read`；
- **秒级实时推送（SSE 长连接）**：`GET /api/v1/notifications/stream` 由服务端主动下发 `{"count": 未读数, "notification": {...}}`——评论落库后立即推送（实测端到端 ~43ms，浏览器红点 ~190ms 点亮、提醒列表原地插入新卡片），标为已读也会推回执让多个标签页同步；连接具备「首帧对齐未读数 + 20s 心跳保活 + 断线指数退避重连」，并保留 15s（未连上）/ 60s（已连上）低频轮询兜底校准。单 worker 用进程内广播中心，多 worker 部署换 Redis pub/sub 即可；
- **未读数实时提示**：顶栏头像红点与个人主页「消息提醒」Tab 双处显示，并在路由切换、窗口重新聚焦、标为已读时立即刷新；
- `search_hits` 热度驱动实时置顶：检索命中最多的前 3 篇博文自动加冕置顶；手动置顶精选由后端校验，仅管理员提交生效，非管理员所传一律忽略；
- 内置 33 个 AI 技术标签库（Transformer / LLM / RAG / Agent / LoRA / 推理优化…），写博时直接选择，管理后台可增删；
- KaTeX 数学公式渲染（含裸露 LaTeX / ASCII 伪代码容错转译）。

### 6. 管理后台
- **控制台外壳**（`AdminLayout.vue`）：浮层式可折叠侧栏（默认收起；展开时以白底投影 + 半透明遮罩覆盖内容区，点击遮罩收起，顶栏与折叠按钮始终可见可点），顶栏为「折叠按钮 + Logo + AI博客论坛控制台」+ 运行状态标识（MySQL 8.0 / 向量知识库），右侧头像下拉含个人主页 / 个人资料 / 写作 / 退出登录，侧栏左下角为「返回博客首页」；
- **运营看板**：「系统运营与知识库大屏」——已发布博文（附草稿箱数）、RAG 向量切片数、全站阅读量、评论互动四张指标卡 + 热文榜（阅读 / 点赞）+ 工程与 AI 技术栈面板，支持一键刷新实时数据；
- **文章管理**：与前台同款搜索胶囊（仅标题匹配、**不**计入门户搜索热度）、按 ID 正序稳定分页、置顶独立列、向量化状态「已索引 / 未索引」、行内「同步向量 / 删除」；
- **标签库运维**：标签增删改（名称 / Slug / 展示色彩三要素）；
- **评论审核**：分页列表 + 公开 / 隐藏即时开关 + 彻底删除；
- **AI 设置**：在线热切换大模型接入商（DeepSeek / 智谱 / OpenAI 或任意 OpenAI 兼容端点），`POST /api/v1/ai/models` 实时拉取可用模型列表，配置回写 `.env`；「一键全量重建」RAG 向量知识库；
- **写作入口**：侧栏「写作」内嵌渲染门户写作组件（保留左侧菜单），保存后回文章列表。

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
│   │   ├── main.py              # FastAPI 装配: CORS / 静态资源 / 全局异常 / 路由注册
│   │   │                        #   + 启动时建表、articles 轻量列迁移、app 命名空间日志
│   │   ├── api/v1/              # RESTful 路由: auth / articles / comments / favorites / tags
│   │   │                        #   notifications / users / statistics / ai_assistant
│   │   ├── api/deps.py          # JWT 鉴权与当前用户依赖注入 (require_admin / get_optional_user)
│   │   ├── core/                # config(Pydantic Settings) / database / security / response(统一封包+全局异常)
│   │   ├── models/              # ORM: user / article / article_chunk / article_tag / tag / comment
│   │   │                        #   article_like / comment_like / favorite / notification / search_log / ai_chat_message
│   │   ├── schemas/             # Pydantic DTO 契约
│   │   └── ai_engine/           # chunking / embedding / retrieval_index(进程级稀疏索引)
│   │                            #   vector_store / rag_service / llm_client / recommendation_service
│   │                            #   tfidf_vectorizer.joblib (持久化词表, 重建时自动生成)
│   ├── seed_data.py             # 建表 + 管理员 + 种子博文 + 向量知识库初始化
│   ├── seed_agent_articles.py   # 批量写入 10 篇 AI Agent 技术栈博文并触发切片建索引
│   ├── migrate_drop_categories.py  # 一次性迁移: 移除分类体系
│   ├── test_api.py              # TestClient 接口冒烟脚本 (健康检查 / 登录 / 文章 / AI)
│   ├── requirements.txt
│   ├── run.py                   # 后端启动入口 (uvicorn, reload=False)
│   └── .env / .env.example      # 本地环境配置 (不入库)
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios 封装 (request.ts 统一拦截/鉴权/错误提示 + 各业务模块)
│   │   ├── components/          # Navbar(顶部搜索胶囊) / AiChatDrawer / ArticleCard
│   │   │                        #   CommentItem / MarkdownViewer / UserProfileModal
│   │   ├── views/
│   │   │   ├── portal/          # 首页 / 文章详情 / 技术标签 / 搜索结果 / 个人主页 / 写作
│   │   │   ├── admin/           # AdminLayout(控制台外壳) / Dashboard / ArticleList
│   │   │   │                    #   TagManage / CommentManage / AiSettings
│   │   │   └── auth/            # 登录注册
│   │   ├── router/              # 路由 + 全局登录守卫 + RBAC 管理员校验
│   │   ├── stores/ · types/ · utils/   # Pinia / TS 契约 / 工具函数
│   │   ├── style.css            # 全局主题变量 (黑曜石黑灰主色) 与滚动条
│   │   └── main.ts · App.vue
│   ├── vite.config.ts           # /api、/static 代理到 127.0.0.1:8000
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
- 后台入口：`http://localhost:5173/admin`（非管理员由全局路由守卫拦回首页）
- Vite 已配置 `/api`、`/static` 代理到 `http://127.0.0.1:8000`，**请先启动后端**：后端未启动时前端页面可打开，但所有数据接口会报错
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
| GET | `/api/v1/articles` | 文章分页列表（关键词 / 标签 / 作者筛选；`title_only=1` 仅标题匹配且不计热度、`order=id_asc` 后台稳定排序；未发布仅作者本人与管理员可见） |
| POST/PUT/DELETE | `/api/v1/articles` `/{id}` `/{id}/reindex` | 发布 / 更新（自动增量重建切片）/ 删除 / 手动重建单篇向量（管理员） |
| GET/POST/PUT/DELETE | `/api/v1/tags` | 标签库读取（公开）与增删改（管理员） |
| GET | `/api/v1/statistics/dashboard` | 后台运营看板聚合统计（管理员） |
| GET | `/api/v1/users/search` | 按用户名 / 昵称模糊搜索用户（公开） |
| GET | `/api/v1/users/{id}/profile` | 用户公开资料（个人主页头部） |
| GET | `/api/v1/comments/my` | 当前用户评论时间线（需登录） |
| GET | `/api/v1/notifications/stream` | 站内提醒实时推送（SSE 长连接：ready 帧对齐未读数 + 新提醒 / 已读回执推送，需登录） |
| * | `/api/v1/auth/*` `/api/v1/comments/*` `/api/v1/favorites/*` `/api/v1/notifications/*` | 鉴权 / 评论 / 收藏 / 通知 |

---

## 常见问题排查

| 现象 | 根因与处理 |
|---|---|
| 语义搜索 / AI 问答返回 500「服务器内部错误」 | 多为**后端进程未重启**：AI 引擎代码改动后旧进程仍在内存中运行旧逻辑，与库内向量维度不匹配。重启后端即可。全局异常拦截器会吞掉真实堆栈，需看后端控制台日志定位。 |
| 重启后相关查询召回为 0 / 相似度异常 | 词表文件 `tfidf_vectorizer.joblib` 缺失或与库内向量不匹配。执行「一键全量重建」重新拟合 + 持久化。 |
| 修改 `.env` 后配置未生效 | `.env` 仅在进程启动时读取；或使用了管理后台热配置（其优先回写 `.env` 并热生效）。修改后请重启后端。 |
| 窗口变窄后后台顶栏右侧（状态标签 / 头像下拉）被裁掉、点不到 | 控制台外壳 `.admin-main-wrap` 是 flex 项，默认 `min-width: auto` 会被 `el-table` 内联写死的像素宽度顶住 —— 整壳宽度锁死在历史最大值，而 `body { overflow-x: hidden }` 又把溢出部分裁掉且无法横向滚动。**处理**：外壳声明 `min-width: 0`（`AdminLayout.vue`），使其始终跟随视口收缩。 |
| 窄窗口下看板右侧面板被推出屏幕 | 同类问题发生在 grid：`1fr` 轨道的 min-content 被内部表格锁死（实测 `993px + 140px` 溢出容器 116px）。**处理**：轨道改 `minmax(0, 1fr)`、栅格子项补 `min-width: 0`（`Dashboard.vue`）。 |
| 后台表格「操作」列两个按钮上下换行、第二个按钮偏右约 6px | 列宽 − 单元格左右内边距 24px 后放不下两个按钮 + 相邻按钮 12px 外边距，触发换行；换行后 `.el-button + .el-button` 的 `margin-left` 落在新行行首，把该行整体推右半格。**处理**：加宽操作列 + 用 `display:flex; justify-content:center; gap` 容器并归零相邻外边距（`TagManage.vue`）。 |

---


