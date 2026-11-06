"""本地发货规则索引和检索，不调用聊天模型进行向量化。"""
from functools import lru_cache
from pathlib import Path
import re

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "data/models/bge-small-zh-v1.5"
DB_PATH = ROOT / "data/chroma"
SOURCE = "knowledge/shipping_rules.md"


@lru_cache(maxsize=1)
def get_store():
    # 模型提前下载到本地，运行服务时不再访问模型下载网站
    embeddings = HuggingFaceEmbeddings(
        model_name=str(MODEL_PATH),
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        collection_name="shipping_rules",
        embedding_function=embeddings,
        persist_directory=str(DB_PATH),
        collection_metadata={"hnsw:space": "cosine"},
    )


def build_index():
    # 按二级标题分割，每条规则单独保存，同时保留文档适用范围
    text = (ROOT / SOURCE).read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)
    documents = []
    for section in sections[1:]:
        match = re.search(r"SHIP-\d+", section)
        if match is None:
            raise ValueError("每个规则章节必须包含 SHIP 编号")
        documents.append(Document(
            page_content=sections[0].strip() + "\n\n## " + section.strip(),
            metadata={"source": SOURCE, "rule_id": match.group(),
                      "title": section.splitlines()[0], "version": "demo-v1"},
        ))
    if not documents:
        raise ValueError("文档中没有找到规则章节")
    store = get_store()
    # 只替换本集合的旧规则，重复执行不会累计重复片段
    old_ids = store.get()["ids"]
    if old_ids:
        store.delete(ids=old_ids)
    store.add_documents(documents, ids=[d.metadata["rule_id"] for d in documents])
    return len(documents)


def search_rules(query: str) -> dict:
    if not query.strip():
        return {"results": [], "message": "请输入需要检索的问题"}
    store = get_store()
    if not store.get(limit=1)["ids"]:
        return {"results": [], "message": "规则索引为空，请先运行索引构建命令"}
    # BGE 中文检索查询前缀；返回距离仅用于排查，不作为事实可信度
    hits = store.similarity_search_with_score(
        "为这个句子生成表示以用于检索相关文章：" + query, k=3,
    )
    return {"results": [
        {**doc.metadata, "content": doc.page_content, "distance": float(distance)}
        for doc, distance in hits
    ], "notice": "结果仅为候选规则；需核对适用范围，不相关时不能作为依据。"}
