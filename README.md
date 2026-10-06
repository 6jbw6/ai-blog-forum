# AI博客论坛 — 基于 RAG 与大模型协同的博客论坛系统

> 面向 **AI 算法 / 大模型应用开发（RAG · Agent · LLM Application）** 方向的全栈实战项目：
> 以博客论坛为业务载体，完整落地工业级 RAG 链路 —— 标题感知切块 → TF-IDF 稀疏向量化 → 进程级倒排索引多路召回 → SSE 流式生成 → 知识溯源引用，并内置账号封禁体系与内容安全审核。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy 2.0 · Pydantic V2 · MySQL 8.0 |
| AI 引擎 | LangChain Text Splitters · Scikit-Learn (TfidfVectorizer) · 自研 Bm25Index (CSC 倒排) · Jieba · OpenAI SDK |
| 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia · Axios · DOMPurify |
| 内容渲染 | Markdown · KaTeX · highlight.js |
| 鉴权 | JWT (PyJWT) · Bcrypt 加盐哈希 · 滑动窗口限流 · RBAC |

---

## 核心功能

### 1. RAG 知识库问答（SSE 流式 + 溯源引用）
- `POST /api/v1/ai/ask` 全链路 SSE 打字机流式输出；
- 回答末尾推送结构化「知识来源卡片」，跨文章取 Top-3，点击直达原文；
- 多轮对话上下文、按账号隔离的对话历史持久化（`ai_chat_messages`）；
- 防幻觉 System Prompt：知识库有据可依、超纲问题坦诚说明、禁止编造。

### 2. 语义检索（稀疏索引 + 多路召回 + 文章级主题判定）
- `POST /api/v1/ai/semantic-search`：自然语言检索博文；
- **进程级稀疏检索索引**（`retrieval_index.py`）：切片向量预拼装为 CSC 倒排矩阵，稠密余弦 / 查询覆盖率 / BM25 三路打分一次遍历完成，快照只读原子替换，请求线程零重建；
- 评分：`0.75 × TF-IDF 余弦 + 0.25 × BM25 饱和映射`，乘标题命中加成；
- **查询侧虚词过滤**：疑问代词等不参与检索（语料侧分词不受影响）；
- 召回门控以「查询词元覆盖率」为主判据（与长短查询无关），阈值可在管理后台热调；
- **搜索单位是文章**：文章级主题判定剔除「仅正文顺带提及」的结果。

### 3. 内容安全与账号封禁体系
- **实时违规监测**：发布评论 / 博文时对文本做敏感词检测（`content_moderation.py` 词库可扩充），命中即**自动封禁**发布者；违规评论保留入库（前台隐藏）供管理员审查处置；
- **人工封号 / 解封**：管理后台「用户管理」按用户名 / 用户 ID 搜索，封禁 / 解封均需弹窗填写原因，原因随账号记录并对用户可见；
- 封禁即时生效：登录被拒（提示原因）、既有 token 立即失效（`get_current_user` 校验 `is_active`）；
- 管理员账号受保护：不可被封禁（含自身）。

### 4. 博客论坛社区
- 多作者发文：前台写作页 `/write`（Markdown 编辑 + 预览，保存草稿 / 公开发布 / 仅自己可见）；
- 公开个人主页 `/user/:id`：博文 / 评论 / 收藏 / 点赞 / 消息提醒多维度；
- 点赞、收藏、树形评论、回复自动派发站内通知与未读红点；
- `search_hits` 热度驱动实时置顶（仅管理员可手动置顶）；
- 33 个 AI 技术标签库；KaTeX 公式渲染。

### 5. 管理后台
- 运营看板（指标卡 + 最受关注博文 Top5，可点击直达原文）；
- 文章管理（仅标题搜索、ID 正序、状态统一「已索引/未索引」、置顶独立列）；
- 评论审核（自动识别不合规评论，只列违规项，跳转原文处置）；
- 标签库、用户管理（搜索 / 封禁 / 解封）；
- AI智能体配置：OpenAI 兼容协议在线接入任意大模型（Base URL + API Key + 在线拉取模型列表），表单输入实时自动保存。

---

## RAG 引擎内部机制（重要）

代码位于 `backend/app/ai_engine/`，检索链路：`chunking.py → embedding.py → retrieval_index.py（进程级稀疏索引）→ vector_store.py → rag_service.py`。

1. **切块**（`chunking.py`）：LangChain `MarkdownHeaderTextSplitter` 按 H1～H4 构建章节面包屑，`RecursiveCharacterTextSplitter`（450 字符 / 60 重叠）保持段落完整。
2. **向量化**（`embedding.py`）：Scikit-Learn `TfidfVectorizer`（Jieba 中英分词 + 停用词 + 词/词对 bigram + sublinear TF）输出 L2 归一化稀疏向量，维度上限 4096（`EMBEDDING_DIM`）。
   > 这是**词法相关度**而非语义嵌入。需要真正语义召回时可启用预留的 `RemoteAPIEmbedder`（OpenAI 兼容嵌入接口）。
3. **词表持久化**：全量重建时 `fit_corpus()` 将词表落盘 `app/ai_engine/tfidf_vectorizer.joblib`，服务启动自动加载（否则查询向量与库内维度语义错位、召回为 0）。
4. **进程级稀疏索引**（`retrieval_index.py`）：CSC 倒排 + 自研 Bm25Index，轻量指纹节流探测变更、后台单飞重建、快照原子替换。
5. **打分与门控**（`vector_store.py`）：覆盖率 ≥ 0.5 或融合分 ≥ 阈值（默认 0.18），再过噪声兜底；展示分与排序分一致，不做归一化拉伸。

### 已知局限
- 语料中没出现过的词搜不到（词法检索固有边界）；
- 小语料下 IDF 语义是「区分度」而非「重要性」，BM25 分量不能单独作判据。

### 运维须知
- 新增 / 修改博文：保存时自动增量重建该文章的切片索引；
- 改动 embedding / 分词 / 切块逻辑后：调用 `POST /api/v1/ai/reindex-all` 全量重建（需先拟合全局词表）；
- **改动 AI 引擎代码后必须重启后端**：`run.py` 以 `reload=False` 运行。

---

## 目录结构

```
ai-blog-forum/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # RESTful 路由: auth / articles / comments / favorites
│   │   │                        #   notifications / ai_assistant / users / admin_users / statistics
│   │   ├── core/                # config / database / security / rate_limit / content_moderation
│   │   ├── models/              # ORM: user / article / article_chunk / search_log / ai_chat_message ...
│   │   ├── schemas/             # Pydantic DTO 契约
│   │   ├── tests/               # pytest: 内存 SQLite 夹具, 鉴权/评论/限流/可见性 22 用例
│   │   └── ai_engine/           # chunking / embedding / retrieval_index / vector_store
│   │                            #   rag_service / llm_client / recommendation_service
│   ├── seed_data.py             # 建表 + 管理员 + 种子博文 + 向量知识库初始化
│   ├── run.py                   # 后端启动入口 (uvicorn)
│   └── .env                     # 本地环境配置 (不入库)
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios 请求封装
│   │   ├── components/          # Navbar / AiChatDrawer / MarkdownViewer ...
│   │   ├── utils/               # validate / sanitize(DOMPurify)
│   │   ├── views/
│   │   │   ├── admin/           # 运营看板 / 文章管理 / 标签库 / 评论审核 / 用户管理 / AI智能体配置
│   │   │   ├── portal/          # 首页 / 详情 / 搜索 / 标签页 / 个人主页 / 写作
│   │   │   └── auth/            # 登录注册
│   │   ├── router/              # 路由 + 全局登录守卫
│   │   └── stores/              # Pinia
│   └── package.json
└── README.md
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

- 复制 `backend/.env.example` 为 `backend/.env`，填写数据库连接、`LLM_API_KEY` 与 `JWT_SECRET_KEY`；
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
- API 服务：`http://127.0.0.1:8000`（Swagger：`http://127.0.0.1:8000/docs`）

### 2. 启动前端
```powershell
cd frontend
npm run dev
```
- 门户地址：`http://localhost:5173`（浏览对游客开放；写作、评论等需登录）

---

## 环境变量（backend/.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接 | 127.0.0.1:3306 / root / ai_blog |
| `JWT_SECRET_KEY` | JWT 签名密钥（必配，强随机值） | - |
| `LLM_PROVIDER` | 大模型接入商标识 | deepseek |
| `LLM_API_KEY` | 大模型密钥（也可在管理后台热配置） | - |
| `LLM_BASE_URL` | OpenAI 兼容端点 | https://api.deepseek.com |
| `LLM_MODEL` | 模型 ID | deepseek-chat |
| `RAG_TOP_K` | 问答注入上下文的切片数 | 4 |
| `RAG_SIMILARITY_THRESHOLD` | 检索相似度阈值 | 0.18 |
| `CORS_ORIGINS` | CORS 允许来源（逗号分隔） | localhost:5173 |
| `LOGIN_RATE_LIMIT` | 登录限流 (次数, 窗口秒) | 10, 60 |

> `pydantic-settings` 按启动时的工作目录读取 `.env`，请务必在 `backend/` 目录下启动 `run.py`。

---

## 主要 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/ai/ask` | RAG 知识库问答（SSE 流式 + 引用卡片） |
| POST | `/api/v1/ai/semantic-search` | 语义检索博文（文章级主题判定） |
| GET | `/api/v1/ai/recommended-questions` | 动态推荐问题（支持换一批） |
| GET | `/api/v1/ai/hot-keywords` | 动态热搜概念 |
| POST | `/api/v1/ai/reindex-all` | 全量重建向量知识库（管理员） |
| GET/PUT | `/api/v1/ai/config` | 读取 / 热更新大模型与 RAG 配置（管理员） |
| GET | `/api/v1/articles` | 文章分页列表（`title_only` / `order=id_asc` 供后台） |
| GET | `/api/v1/users/search` | 按用户名 / 昵称模糊搜索用户（公开） |
| GET | `/api/v1/users/{id}/profile` | 用户公开资料 |
| GET | `/api/v1/admin/users?keyword=` | 用户管理搜索（用户名 / 昵称 / ID，管理员） |
| POST | `/api/v1/admin/users/{id}/ban` | 封禁账号（原因必填，管理员） |
| POST | `/api/v1/admin/users/{id}/unban` | 解封账号（原因必填，管理员） |
| GET | `/api/v1/comments/admin/list` | 违规评论审查列表（管理员） |
| * | `/api/v1/auth/*` `/api/v1/comments/*` `/api/v1/favorites/*` `/api/v1/notifications/*` | 鉴权 / 评论 / 收藏 / 通知 |

---

## 常见问题排查

| 现象 | 根因与处理 |
|---|---|
| 语义搜索 / AI 问答返回 500 | 多为后端进程未重启（AI 引擎代码改动后旧进程仍运行）。重启后端，看控制台日志定位。 |
| 重启后相关查询召回为 0 | 词表 `tfidf_vectorizer.joblib` 缺失或不匹配，执行全量重建。 |
| 登录报「JWT 密钥未配置」 | `.env` 缺 `JWT_SECRET_KEY`，生成强随机值填入并重启。 |
| 修改 `.env` 后配置未生效 | `.env` 仅启动时读取；管理后台热配置会回写 `.env` 并热生效。修改后请重启后端。 |

---

## 测试

```powershell
cd backend
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest -v
```
覆盖：登录鉴权、评论链路、限流、草稿/私有可见性等 22 个用例（内存 SQLite，不动业务库）。
