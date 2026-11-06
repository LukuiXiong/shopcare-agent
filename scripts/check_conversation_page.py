"""验证空白对话不落库，以及历史恢复；不调用模型。"""
import sqlite3
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

base = 'http://127.0.0.1:8002'
for _ in range(45):
    try:
        if httpx.get(base+'/health',timeout=2).status_code == 200: break
    except httpx.HTTPError: pass
    time.sleep(1)
else: raise RuntimeError('服务未就绪')

def count():
    with sqlite3.connect(Path('data/chat.sqlite3')) as db:
        return db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]

before=count()
rows=httpx.get(base+'/conversations').json()
assert all(row['title'] != '新对话' for row in rows)
cid=rows[0]['id'] if rows else None
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1000,'height':800})
    page.goto(base)
    page.wait_for_function('!busy')
    assert page.locator('#welcome').is_visible()
    for _ in range(5):
        page.click('#clear')
        page.wait_for_function('!busy')
    page.reload()
    page.wait_for_function('!busy')
    assert count()==before
    page.fill('#input','你好')
    assert page.locator('#send').is_enabled()
    if cid:
        page.select_option('#history',cid)
        page.wait_for_function('!busy && document.querySelectorAll(".message").length > 0')
        size=page.locator('.message').count()
        page.reload();page.wait_for_function('!busy')
        assert page.locator('.message').count()==size
        page.click('#clear');page.wait_for_function('!busy')
        assert page.locator('.message').count()==0
    # 旧编号失效时恢复空白，不新增数据库记录。
    page.evaluate("localStorage.setItem('shopcare.conversation','00000000-0000-0000-0000-000000000000')")
    page.reload();page.wait_for_function('!busy')
    assert page.locator('#welcome').is_visible()
    assert page.evaluate('conversationId') is None
    # 模拟回复验证首次不带会话编号，后续携带返回编号；不产生模型费用或测试会话。
    if cid:
        sent=[]
        def answer(route):
            sent.append(route.request.post_data_json)
            route.fulfill(json={'reply':'测试回复','conversation_id':cid})
        page.route('**/chat',answer)
        page.fill('#input','第一条测试');page.click('#send');page.wait_for_function('!busy')
        assert sent[0]['conversation_id'] is None
        page.fill('#input','第二条测试');page.click('#send');page.wait_for_function('!busy')
        assert sent[1]['conversation_id']==cid
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert count()==before
    browser.close()
print('空白打开、重复新建、刷新均不落库；旧编号回退、历史恢复及手机宽度通过')
