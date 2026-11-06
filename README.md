# ShopCare 电商售后助手

基于 FastAPI、LangGraph、MCP 和 RAG 的本地电商售后演示项目。

支持模拟订单查询、发货规则检索、Time MCP 超时判断、SQLite 催发货工单登记/查询/关闭，以及持久化多轮聊天网页。

## 本地启动

需要 Python 3.12+ 和 uv。在项目根目录执行：

```powershell
# 安装锁定版本的依赖
uv sync --locked
# 自行创建本地 .env，填写 MODEL_NAME 和 DEEPSEEK_API_KEY，不要提交密钥
# 首次启动前准备本地 embedding 模型和检索索引
uv run python -m scripts.build_index
# 启动服务，打开 http://127.0.0.1:8002/
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

模型初始化保留 `load_dotenv()` 和 `init_chat_model()`。本地 BGE 模型和 Chroma 索引的准备步骤见 `knowledge/RAG_USAGE.md`。

## 验证

```powershell
# 固定时间边界验证
uv run python -m scripts.check_shipping
# 工单验证使用临时数据库
uv run python -m scripts.check_tickets
uv run python -m scripts.check_ticket_query
uv run python -m scripts.check_ticket_close
# 会话持久化验证
uv run python -m scripts.check_conversations
```

## 数据与限制

订单及规则均为演示数据，不连接真实店铺或通知商家。关闭工单不代表商家已处理或订单已发货。

本项目面向本机单进程演示，无登录与用户隔离。聊天和工单保存在 `data/`，请保留本地数据库。调用真实模型可能产生费用。

`.env`、上下文交接文档、数据库、模型、向量索引、日志及虚拟环境均不上传仓库。换机时需自行配置环境和准备模型/索引。
