import os
import re
import sys
import requests
from markdownify import markdownify as md
from dotenv import load_dotenv
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

BASE_URL   = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
EMAIL      = os.getenv("CONFLUENCE_EMAIL", "")
API_TOKEN  = os.getenv("CONFLUENCE_API_TOKEN", "")
SPACE_KEY  = os.getenv("CONFLUENCE_SPACE_KEY", "MC")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "~/Desktop")).expanduser() / "confluence_md"

session = requests.Session()
session.auth = (EMAIL, API_TOKEN)
session.headers.update({"Accept": "application/json"})

user_cache = {}

def get_user_display_name(account_id):
    if account_id in user_cache:
        return user_cache[account_id]
    try:
        resp = session.get(f"{BASE_URL}/wiki/rest/api/user", params={"accountId": account_id})
        name = resp.json().get("displayName", account_id) if resp.ok else account_id
    except Exception:
        name = account_id
    user_cache[account_id] = name
    return name

def resolve_user_mentions(html):
    def replace_user_link(m):
        return f'<strong>@{get_user_display_name(m.group(1))}</strong>'
    html = re.sub(r'<ac:link>\s*<ri:user[^>]*ri:account-id="([^"]+)"[^/]*/>\s*</ac:link>', replace_user_link, html)
    html = re.sub(r'<ri:user[^>]*ri:account-id="([^"]+)"[^/]*/?>', replace_user_link, html)
    return html

def get_all_pages():
    pages = []
    start = 0
    limit = 100
    print(f"Varrendo space '{SPACE_KEY}'...")
    while True:
        resp = session.get(f"{BASE_URL}/wiki/rest/api/content", params={"spaceKey": SPACE_KEY, "type": "page", "status": "current", "start": start, "limit": limit, "expand": "ancestors,version,metadata.labels"})
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        pages.extend(results)
        print(f"   -> {len(pages)} paginas encontradas...")
        if len(results) < limit:
            break
        start += limit
    print(f"Total: {len(pages)} paginas.\n")
    return pages

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text[:80]

def get_folder_path(page):
    folder = OUTPUT_DIR
    for ancestor in page.get("ancestors", []):
        folder = folder / slugify(ancestor["title"])
    return folder

def get_page_content(page_id):
    resp = session.get(f"{BASE_URL}/wiki/api/v2/pages/{page_id}", params={"body-format": "storage"})
    if resp.ok:
        html = resp.json().get("body", {}).get("storage", {}).get("value", "")
        if html:
            return html
    resp = session.get(f"{BASE_URL}/wiki/rest/api/content/{page_id}", params={"expand": "body.storage"})
    resp.raise_for_status()
    return resp.json()["body"]["storage"]["value"]

def html_to_markdown(html):
    html = resolve_user_mentions(html)
    html = re.sub(r'<time[^>]*datetime="([^"]+)"[^>]*/?>',r'\1', html)
    html = re.sub(r'<ac:task-list[^>]*>', '<ul>', html)
    html = re.sub(r'</ac:task-list>', '</ul>', html)
    html = re.sub(r'<ac:task-status>complete</ac:task-status>', '[x]', html)
    html = re.sub(r'<ac:task-status>incomplete</ac:task-status>', '[ ]', html)
    html = re.sub(r'<ac:task-id>.*?</ac:task-id>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:task-uuid>.*?</ac:task-uuid>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:task[^>]*>', '>', html)
    html = re.sub(r'</ac:task>', '</li>', html)
    html = re.sub(r'</?ac:task-body[^>]*>', '', html)

    def extract_macro_body(m):
        name = re.search(r'ac:name="(\w+)"', m.group(0))
        label = name.group(1).upper() if name else "NOTA"
        body = re.search(r'<ac:rich-text-body[^>]*>(.*?)</ac:rich-text-body>', m.group(0), re.DOTALL)
        inner = body.group(1) if body else ""
        return f'<blockquote><strong>[{label}]</strong><br/>{inner}</blockquote>'

    html = re.sub(r'<ac:structured-macro[^>]*ac:name="(?:info|note|warning|tip|panel)"[^>]*>.*?</ac:structured-macro>', extract_macro_body, html, flags=re.DOTALL)
    html = re.sub(r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?<ac:plain-text-body[^>]*><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?</ac:structured-macro>', r'<pre>de>\1</code></pre>', html, flags=re.DOTALL)

    def extract_expand(m):
        title = re.search(r'<ac:parameter[^>]*ac:name="title"[^>]*>(.*?)</ac:parameter>', m.group(0), re.DOTALL)
        t = title.group(1).strip() if title else "Expandir"
        body = re.search(r'<ac:rich-text-body[^>]*>(.*?)</ac:rich-text-body>', m.group(0), re.DOTALL)
        inner = body.group(1) if body else ""
        return f'<details><summary>{t}</summary>{inner}</details>'

    html = re.sub(r'<ac:structured-macro[^>]*ac:name="expand"[^>]*>.*?</ac:structured-macro>', extract_expand, html, flags=re.DOTALL)
    html = re.sub(r'<ac:structured-macro[^>]*>', '', html)
    html = re.sub(r'</ac:structured-macro>', '', html)
    html = re.sub(r'</?ac:rich-text-body[^>]*>', '', html)
    html = re.sub(r'<ac:parameter[^>]*>.*?</ac:parameter>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:plain-text-body[^>]*>.*?</ac:plain-text-body>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:adf-attribute[^>]*>.*?</ac:adf-attribute>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ac:adf-fallback[^>]*>.*?</ac:adf-fallback>', '', html, flags=re.DOTALL)
    html = re.sub(r'</?ac:adf-content[^>]*>', '', html)
    html = re.sub(r'</?ac:adf[^>]*>', '', html)
    html = re.sub(r'<ac:[^>]+/>', '', html)
    html = re.sub(r'<ac:[^>]+>.*?</ac:[^>]+>', '', html, flags=re.DOTALL)
    html = re.sub(r'<ri:[^>]+/>', '', html)
    html = re.sub(r'<ri:[^>]+>.*?</ri:[^>]+>', '', html, flags=re.DOTALL)
    html = re.sub(r'\s+local-id="[^"]*"', '', html)
    result = md(html, heading_style="ATX", bullets="-")
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()

def build_header(page):
    title = page.get("title", "Sem titulo")
    version = page.get("version", {})
    author = version.get("by", {}).get("displayName", "Desconhecido")
    modified = version.get("when", "")[:10]
    labels = [l["name"] for l in page.get("metadata", {}).get("labels", {}).get("results", [])]
    label_str = ", ".join(labels) if labels else "-"
    ancestors = page.get("ancestors", [])
    path_str = " > ".join(a["title"] for a in ancestors) + f" > {title}" if ancestors else title
    header  = f"# {title}\n\n"
    header += f"> **Caminho:** {path_str}  \n"
    header += f"> **Autor:** {author}  \n"
    header += f"> **Ultima modificacao:** {modified}  \n"
    header += f"> **Labels:** {label_str}  \n\n"
    header += "---\n\n"
    return header

def run():
    for var, val in [("CONFLUENCE_BASE_URL", BASE_URL), ("CONFLUENCE_EMAIL", EMAIL), ("CONFLUENCE_API_TOKEN", API_TOKEN)]:
        if not val:
            raise SystemExit(f"Variavel {var} nao definida no .env")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Salvando em: {OUTPUT_DIR}\n")
    pages = get_all_pages()
    ok, erros = 0, []
    for i, page in enumerate(pages, 1):
        page_id = page["id"]
        title = page["title"]
        print(f"[{i}/{len(pages)}] {title}")
        try:
            folder = get_folder_path(page)
            folder.mkdir(parents=True, exist_ok=True)
            filepath = folder / (slugify(title) + ".md")
            html = get_page_content(page_id)
            markdown = html_to_markdown(html)
            header = build_header(page)
            content = header + (markdown if markdown.strip() else "*Pagina sem conteudo.*")
            filepath.write_text(content, encoding="utf-8")
            ok += 1
        except Exception as e:
            print(f"   ERRO: {e}")
            erros.append(title)
    print(f"\n{'='*50}")
    print(f"{ok} paginas salvas em: {OUTPUT_DIR}")
    if erros:
        print(f"{len(erros)} paginas com erro:")
        for t in erros:
            print(f"   - {t}")

if __name__ == "__main__":
    run()
