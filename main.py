from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from contextlib import AsyncExitStack
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.conversations import ConversationStore
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from app.agent import create_agent
from app.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 使用当前虚拟环境的 Python 和绝对路径，避免启动目录影响工具进程
    server_path = Path(__file__).resolve().parent / "mcp_server.py"
    client = MultiServerMCPClient({
        "orders": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(server_path)],
        }
    })
    # 在同一个生命周期内保持连接，退出时自动关闭会话及子进程
    async with client.session("orders") as session:
        tools = await load_mcp_tools(session)
        # 聊天数据库独立于工单库；连接随服务启动和关闭。
        async with AsyncExitStack() as async_stack:
            store = ConversationStore(Path(__file__).resolve().parent / "data" / "chat.sqlite3")
            await store.setup()
            saver = await async_stack.enter_async_context(AsyncSqliteSaver.from_conn_string(str(store.path)))
            await saver.setup()
            app.state.conversations = store
            app.state.agent = create_agent(tools, saver)
            try:
                yield
            finally:
                app.state.agent = None



# 创建 FastAPI 应用，title 会显示在接口文档页面上
app = FastAPI(title="电商售后助手", lifespan=lifespan)

# 注册聊天路由，使 POST /chat 使用真实模型回答
app.include_router(chat_router)

# 使用绝对路径提供聊天页面，避免终端启动目录影响文件查找
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def chat_page():
    # 页面与 /chat 同源，不需要额外配置跨域
    return FileResponse(STATIC_DIR / "index.html")

# 定义健康检查接口，方便确认服务是否正常运行
# GET 表示读取数据，/health 是接口路径
@app.get("/health")
def health():
    # 返回字典，FastAPI 会自动将它转换为 JSON
    return {"status": "ok"}


