import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from app.schemas import ChatRequest, ChatResponse
from app.conversations import graph_config

router = APIRouter(tags=["聊天"])


@router.get('/conversations')
async def list_conversations(request: Request):
    # 本机演示无登录，列表属于本服务，不提供用户隔离。
    return await request.app.state.conversations.list()


@router.get('/conversations/{conversation_id}')
async def get_conversation(conversation_id: UUID, request: Request):
    store = request.app.state.conversations
    cid = str(conversation_id)
    async with store.lock(cid):
        row = await store.get(cid)
        if row is None:
            raise HTTPException(404, '会话不存在')
        messages = []
        if row['checkpoint_id']:
            state = await request.app.state.agent.aget_state(graph_config(row))
            # 页面只显示用户消息和最终回复，不展示内部工具结果。
            for msg in state.values.get('messages', []):
                if msg.type == 'human' or (msg.type == 'ai' and not msg.tool_calls):
                    messages.append({'role': 'user' if msg.type == 'human' else 'assistant', 'text': msg.text})
        return {'id': cid, 'title': row['title'], 'messages': messages}


@router.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    if not request.message.strip():
        raise HTTPException(422, '消息不能为空')
    store = http_request.app.state.conversations
    cid = str(request.conversation_id) if request.conversation_id else (await store.create())['id']
    async with store.lock(cid):
        row = await store.get(cid)
        if row is None:
            raise HTTPException(404, '会话不存在')
        try:
            agent = http_request.app.state.agent
            # 指定上次成功检查点：失败分支不会在下一轮被自动续跑。
            result = await agent.ainvoke({'messages': [('human', request.message)]}, config=graph_config(row))
            reply = result['messages'][-1].text
            state = await agent.aget_state({'configurable': {'thread_id': row['graph_id']}})
            await store.complete(cid, state.config['configurable']['checkpoint_id'], request.message)
        except asyncio.CancelledError:
            await store.discard_initial_failure(cid)
            raise
        except Exception:
            await store.discard_initial_failure(cid)
            raise HTTPException(502, '助手处理失败；如涉及登记，请先查询工单确认结果。') from None
    return ChatResponse(reply=reply, conversation_id=cid)
