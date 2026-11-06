"""浏览器验证：uv run --with playwright python -m scripts.check_markdown。"""
from playwright.sync_api import sync_playwright


if __name__ == "__main__":
    with sync_playwright() as p:
        # 使用本机 Chrome，无需下载浏览器或修改项目依赖
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True,
        )
        page = browser.new_page(viewport={"width": 1000, "height": 800})
        page.goto("http://127.0.0.1:8002/")
        text = "**工单编号**：SHIP-123\n\n- 状态：待处理\n\n|字段|值|\n|---|---|\n|订单|ORD1002|\n\n<img src=x onerror=alert(1)><script>alert(1)</script>[危险链接](javascript:alert(1))"
        page.evaluate("text => addMessage('assistant', text)", text)
        assert page.locator(".markdown strong").inner_text() == "工单编号"
        assert page.locator(".markdown li").count() == 1
        assert page.locator(".markdown table").count() == 1
        assert page.locator(".markdown img,.markdown script,.markdown [onerror]").count() == 0
        assert page.locator('.markdown a[href^="javascript:"]').count() == 0
        page.evaluate("addMessage('user', '**原文** <img src=x>')")
        assert page.locator(".user .bubble").inner_text() == "**原文** <img src=x>"
        # 资源不可用时回退纯文本，不执行未经净化的 HTML
        page.evaluate("window.DOMPurify = undefined; addMessage('assistant', '**回退原文**')")
        assert page.locator(".assistant").last.locator(".bubble").inner_text() == "**回退原文**"
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()
    print("加粗、列表、表格、安全过滤、用户原文、回退和移动端宽度检查通过")
