"""临时数据库验证会话持久化、隔离和失败分支，不调用付费模型或工单工具。"""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from langchain.messages import AIMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.conversations import ConversationStore, graph_config


async def run():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / 'chat.sqlite3'
        store = ConversationStore(path)
        await store.setup()
        a, b = await store.create(), await store.create()
        async def answer(state):
            if state['messages'][-1].text == '失败':
                raise ValueError('模拟模型失败')
            return {'messages': [AIMessage(content='|'.join(m.text for m in state['messages'] if m.type == 'human'))]}
        builder = StateGraph(MessagesState)
        builder.add_node('assistant', answer)
        builder.add_edge(START, 'assistant')
        async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
            graph = builder.compile(checkpointer=saver)
            async def send(row, text):
                result = await graph.ainvoke({'messages': [('human', text)]}, graph_config(row))
                state = await graph.aget_state({'configurable': {'thread_id': row['graph_id']}})
                await store.complete(row['id'], state.config['configurable']['checkpoint_id'], text)
                return result['messages'][-1].text
            assert await send(a, 'ORD1002') == 'ORD1002'
            a = await store.get(a['id'])
            try:
                await send(a, '失败')
            except ValueError:
                pass
            assert await send(a, '它呢') == 'ORD1002|它呢'
            assert await send(b, '你好') == '你好'
            empty = await store.create()
            old = empty['graph_id']
            await store.discard_initial_failure(empty['id'])
            assert (await store.get(empty['id']))['graph_id'] != old
            assert len(await store.list()) == 2
            # 同会话锁确保并发请求按顺序读取最新检查点。
            async def serial(text):
                async with store.lock(a['id']):
                    return await send(await store.get(a['id']), text)
            results = await asyncio.gather(serial('甲'), serial('乙'))
            assert results[-1] == 'ORD1002|它呢|甲|乙'
        # 关闭后重开连接，模拟服务重启。
        async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
            state = await builder.compile(checkpointer=saver).aget_state(graph_config(await store.get(a['id'])))
            assert state.values['messages'][-1].text == 'ORD1002|它呢|甲|乙'
    print('会话持久化、隔离、失败分支、首轮失败及并发验证通过')


if __name__ == '__main__':
    asyncio.run(run())
