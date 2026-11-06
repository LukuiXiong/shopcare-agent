"""本机会话元数据；检查点正文由 LangGraph 保存，不接触工单库。"""
import asyncio
from uuid import uuid4
from pathlib import Path
import aiosqlite


class ConversationStore:
    def __init__(self, path: Path):
        self.path = path
        # 单进程本地部署：同一会话串行，防止并发覆盖上下文。
        self.locks: dict[str, asyncio.Lock] = {}

    async def setup(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, graph_id TEXT NOT NULL,
                checkpoint_id TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            await db.commit()

    def lock(self, conversation_id):
        return self.locks.setdefault(conversation_id, asyncio.Lock())

    async def create(self):
        cid = str(uuid4())
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO conversations(id,title,graph_id) VALUES(?,?,?)',
                             (cid, '新对话', str(uuid4())))
            await db.commit()
        return await self.get(cid)

    async def get(self, cid):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM conversations WHERE id=?', (cid,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def list(self):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT id,title,updated_at FROM conversations WHERE checkpoint_id IS NOT NULL ORDER BY updated_at DESC, rowid DESC') as cur:
                return [dict(row) for row in await cur.fetchall()]

    async def complete(self, cid, checkpoint_id, title):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''UPDATE conversations SET checkpoint_id=?,
                title=CASE WHEN checkpoint_id IS NULL THEN ? ELSE title END,
                updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=?''',
                (checkpoint_id, title[:40], cid))
            await db.commit()

    async def discard_initial_failure(self, cid):
        # 首轮没有成功检查点时更换图标识，后续不恢复失败图的待执行工具。
        async with aiosqlite.connect(self.path) as db:
            await db.execute('UPDATE conversations SET graph_id=? WHERE id=? AND checkpoint_id IS NULL',
                             (str(uuid4()), cid))
            await db.commit()


def graph_config(row):
    config = {'thread_id': row['graph_id']}
    if row['checkpoint_id']:
        config['checkpoint_id'] = row['checkpoint_id']
    return {'configurable': config, 'recursion_limit': 16}
