from typing import List, Dict, Any
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class MarkdownChunker:
    """
    基于 LangChain 官方工业级标准分块器 (LangChain MarkdownHeaderTextSplitter & RecursiveCharacterTextSplitter)
    
    核心优势:
    1. 结构感知：使用 LangChain 的 MarkdownHeaderTextSplitter 按 Markdown 标题层级（H1~H4）精准抽取结构化元数据；
    2. 递归细分：对长段落采用 RecursiveCharacterTextSplitter，优先按自然段落、中文句读标点分块并保持 Overlap 滑动窗口；
    3. 标准化上下文注入：自动维护完整的章节层级路径（Breadcrumb），提升 RAG 向量召回精确率与可溯源性。
    """

    def __init__(self, target_chunk_size: int = 450, chunk_overlap: int = 60):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

        # 配置 LangChain 标题切分规则
        self.headers_to_split_on = [
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
            ("####", "h4"),
        ]
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on,
            strip_headers=False
        )
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.target_chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", ". ", " ", ""]
        )

    def split_text(self, title: str, content: str) -> List[Dict[str, Any]]:
        """使用 LangChain 标准管道将博文解析切分为上下文感知的切片列表"""
        if not content or not content.strip():
            return []

        # 1. 结构切分 (提取标题树)
        try:
            header_docs = self.header_splitter.split_text(content)
        except Exception:
            header_docs = []

        # 2. 递归细分
        if header_docs:
            docs = self.recursive_splitter.split_documents(header_docs)
        else:
            docs = self.recursive_splitter.create_documents([content])

        chunks: List[Dict[str, Any]] = []
        for d in docs:
            # 提取标题路径
            meta_headings = [v for k, v in d.metadata.items() if k in ("h1", "h2", "h3", "h4")]
            if meta_headings:
                heading_path = " > ".join(meta_headings)
                chunk_title = f"{title} > {heading_path}"
                chunk_content = f"【章节: {heading_path}】\n{d.page_content.strip()}"
            else:
                chunk_title = title
                chunk_content = f"【文章: {title}】\n{d.page_content.strip()}"

            chunks.append({
                "title": chunk_title,
                "content": chunk_content,
                "token_count": len(d.page_content)
            })

        # 保底处理：如果无有效分块，直接生成单一分块
        if not chunks and content.strip():
            chunks.append({
                "title": title,
                "content": f"【文章: {title}】\n{content.strip()}",
                "token_count": len(content)
            })

        return chunks
