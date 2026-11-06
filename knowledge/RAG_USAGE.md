# 本地发货规则检索

知识来源是 shipping_rules.md，仅用于模拟店铺。

## 更新规则

先停止服务，再修改文档并执行以下命令，最后重新启动服务。
不要在服务查询期间重建索引；服务进程缓存了向量库连接和模型。

```powershell
# 在项目根目录重建规则索引，已下载模型会直接复用
uv run python -m scripts.build_index
# 检查五类问题是否匹配对应规则
uv run python -m scripts.check_retrieval
# 启动本地服务，8002 为本次部署使用的端口
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

## 调用链

离线建库：Markdown → 按二级标题切分为五条规则 → BGE 中文模型向量化 → Chroma 本地持久化。

在线问答：POST /chat → LangGraph 模型节点 → MCP Client → stdio MCP Server → search_shipping_rules → BGE 查询向量 → Chroma 相似度检索前三条 → 返回正文、编号和来源 → 模型生成带引用的回答。

模型保存在 data/models，索引保存在 data/chroma，不提交到版本库。
每个 MCP 进程启动时预加载 CPU 模型，后续查询复用。
当前订单没有付款时间和发货截止时间，因此不能直接判断具体订单是否超时；没有创建工单工具。
