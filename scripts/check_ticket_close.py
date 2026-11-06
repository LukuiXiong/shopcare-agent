"""临时数据库验证关闭、旧表迁移、并发及重新登记，不修改演示工单。"""
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from functools import partial

from app.tickets import close_shipping_ticket, save_shipping_reminder, find_shipping_reminders
import mcp_server


async def check(path):
    async def fixed_time():
        return '2026-11-06T10:00:00+08:00'

    closer = partial(close_shipping_ticket, db_path=path)
    with patch.object(mcp_server, 'read_current_time', fixed_time), patch('app.tickets.close_shipping_ticket', closer):
        first = await mcp_server.close_shipping_reminder('SHIP-old', '用户不再需要催发货')
        assert first['success'] and first['closed']
        again = await mcp_server.close_shipping_reminder('SHIP-old', '另一个备注')
        assert again['success'] and not again['closed']
        assert again['ticket'] == first['ticket']
        assert not (await mcp_server.close_shipping_reminder("' OR 1=1 --"))['success']
        assert not (await mcp_server.close_shipping_reminder('SHIP-old', 'x'*501))['success']
        saver = partial(save_shipping_reminder, db_path=path)
        with patch('app.tickets.save_shipping_reminder', saver):
            new = await mcp_server.create_shipping_reminder('ORD1002')
            assert new['created'] and new['ticket']['ticket_id'] != 'SHIP-old'
        async def broken_time():
            raise RuntimeError('取时失败')
        with patch.object(mcp_server, 'read_current_time', broken_time):
            assert not (await mcp_server.close_shipping_reminder(new['ticket']['ticket_id']))['success']
        assert find_shipping_reminders('ORD1002', path)[0]['status'] == 'open'
    ticket_id = new['ticket']['ticket_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: closer(ticket_id, fixed_time_value, str(n)), range(8)))
    assert sum(r['closed'] for r in results) == 1
    rows = find_shipping_reminders('ORD1002', path)
    assert len(rows) == 2 and all(r['status'] == 'closed' for r in rows)


fixed_time_value = '2026-11-06T10:00:00+08:00'
if __name__ == '__main__':
    with TemporaryDirectory() as folder:
        path = Path(folder)/'tickets.sqlite3'
        assert not close_shipping_ticket('missing', fixed_time_value, '测试', path)['success']
        assert not path.exists()
        # 模拟旧版本五列表，验证升级不丢原始工单。
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE tickets(ticket_id TEXT PRIMARY KEY,order_id TEXT,type TEXT,status TEXT,created_at TEXT)')
            db.execute("INSERT INTO tickets VALUES('SHIP-old','ORD1002','shipping_reminder','open','2026-11-05T10:00:00+08:00')")
        db.close()
        asyncio.run(check(path))
    print('关闭、重复关闭、旧表迁移、取时失败、并发和重新登记检查通过')
