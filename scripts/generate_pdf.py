"""Generate a PDF from docs/user-manual.md using markdown → HTML → Chrome CDP."""

import base64
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import markdown
import websocket

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
MD_PATH = DOCS_DIR / "user-manual.md"
PDF_PATH = DOCS_DIR / "user-manual.pdf"

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
CDP_PORT = 9223

CSS = """\
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 780px;
    margin: 0 auto;
    padding: 20px;
    font-size: 13px;
    line-height: 1.6;
    color: #333;
}
h1 { color: #009688; border-bottom: 2px solid #009688; padding-bottom: 8px; }
h2 { color: #00796b; margin-top: 2em; }
h3 { color: #004d40; }
h4 { color: #333; }
code {
    background: #f5f5f5; padding: 2px 6px; border-radius: 3px;
    font-size: 12px; font-family: 'Cascadia Code', 'Consolas', monospace;
}
pre {
    background: #263238; color: #eeffff; padding: 16px; border-radius: 6px;
    overflow-x: auto; font-size: 12px;
}
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 12px; }
th { background: #009688; color: white; }
tr:nth-child(even) { background: #f9f9f9; }
img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; margin: 1em 0; }
blockquote {
    border-left: 4px solid #009688; margin: 1em 0;
    padding: 0.5em 1em; background: #e0f2f1;
}
hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
a { color: #009688; }
"""


FOOTER_TEMPLATE = (
    '<div style="font-size:9px; width:100%; text-align:center; color:#999;">'
    '<span class="pageNumber"></span> / <span class="totalPages"></span>'
    "</div>"
)


def _cdp_call(ws: websocket.WebSocket, method: str, params: dict | None = None) -> dict:
    """Send a CDP command and return the result."""
    msg_id = int(time.monotonic() * 1000)
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            if "error" in resp:
                raise RuntimeError(f"CDP error: {resp['error']}")
            return resp.get("result", {})


def _embed_images(text: str, base_dir: Path) -> str:
    """Replace relative image paths with base64 data URIs."""

    def _replacer(m: re.Match[str]) -> str:
        alt, src = m.group(1), m.group(2)
        img_path = base_dir / src
        if img_path.exists():
            data = base64.b64encode(img_path.read_bytes()).decode()
            return f"![{alt}](data:image/png;base64,{data})"
        return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replacer, text)


def main() -> None:
    md_text = MD_PATH.read_text(encoding="utf-8")
    md_text = _embed_images(md_text, DOCS_DIR)

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"],
    )

    html_doc = (
        "<!DOCTYPE html>\n"
        '<html><head><meta charset="utf-8">\n'
        f"<style>{CSS}</style>\n"
        f"</head><body>{html_body}</body></html>"
    )

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html_doc)
        html_path = Path(f.name)

    # Launch Chrome with remote debugging
    user_data = tempfile.mkdtemp(prefix="chrome_pdf_")
    chrome_proc = subprocess.Popen(
        [
            str(CHROME),
            f"--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={user_data}",
            html_path.as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for CDP to be ready
        ws_url = None
        for _ in range(50):
            try:
                resp = urlopen(f"http://127.0.0.1:{CDP_PORT}/json")
                tabs = json.loads(resp.read())
                for tab in tabs:
                    if tab.get("type") == "page":
                        ws_url = tab["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if not ws_url:
            print("ERROR: Could not connect to Chrome CDP", file=sys.stderr)
            sys.exit(1)

        ws = websocket.create_connection(ws_url)

        # Wait for the page to finish loading
        _cdp_call(ws, "Page.enable")
        time.sleep(1)  # let images render

        # Print to PDF with custom footer (page numbers only), no header
        result = _cdp_call(
            ws,
            "Page.printToPDF",
            {
                "displayHeaderFooter": True,
                "headerTemplate": "<span></span>",
                "footerTemplate": FOOTER_TEMPLATE,
                "marginTop": 0.6,
                "marginBottom": 0.6,
                "marginLeft": 0.4,
                "marginRight": 0.4,
                "printBackground": True,
            },
        )

        pdf_data = base64.b64decode(result["data"])
        PDF_PATH.write_bytes(pdf_data)

        ws.close()
    finally:
        chrome_proc.terminate()
        chrome_proc.wait(timeout=5)
        html_path.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(user_data, ignore_errors=True)

    size_kb = PDF_PATH.stat().st_size // 1024
    print(f"PDF created: {PDF_PATH} ({size_kb} KB)")

    size_kb = PDF_PATH.stat().st_size // 1024
    print(f"PDF created: {PDF_PATH} ({size_kb} KB)")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
