# viewer_server.py
import os
import io
from pathlib import Path
from flask import Flask, send_file, render_template_string, abort, request, url_for
import fitz  # PyMuPDF
from PIL import Image

FOUNDATIONS_PATH = Path(__file__).parent / "FOUNDATIONS"
THUMB_MAX_W = 360  # px

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<title>PDF Viewer — FOUNDATIONS</title>
<style>
body{font-family:system-ui,Segoe UI,Arial;margin:18px}
.grid{display:flex;flex-wrap:wrap;gap:16px}
.card{width:360px;border:1px solid #ddd;padding:10px;border-radius:8px}
.thumb{width:100%;height:auto;background:#f6f6f6;display:block}
.meta{margin-top:8px;display:flex;justify-content:space-between;align-items:center}
.controls{margin-top:10px}
.controls a{margin-right:8px}
</style>
<h2>FOUNDATIONS PDFs</h2>
<p>Click a thumbnail to open the PDF page in the viewer.</p>
<div class="grid">
{% for p in pdfs %}
  <div class="card">
    <a href="{{ url_for('view_pdf', name=p['name']) }}">
      <img class="thumb" src="{{ url_for('thumb', name=p['name']) }}" alt="thumb">
    </a>
    <div class="meta">
      <div><strong>{{ p['name'] }}</strong><div style="font-size:0.9em;color:#555">{{ p['pages'] }} pages</div></div>
      <div><a href="{{ url_for('download', name=p['name']) }}">Download</a></div>
    </div>
  </div>
{% endfor %}
</div>
"""

VIEW_HTML = """
<!doctype html>
<title>{{ name }}</title>
<style>body{font-family:system-ui;margin:12px} .toolbar{margin-bottom:8px} img{max-width:100%;height:auto;display:block;margin:8px 0}</style>
<div class="toolbar">
  <a href="{{ url_for('index') }}">← Back</a>
  <span style="margin-left:12px">Viewing: <strong>{{ name }}</strong> — page {{ page+1 }}/{{ pages }}</span>
  <span style="margin-left:12px">
    <a href="{{ url_for('view_pdf', name=name, page=page-1) }}" {% if page<=0 %}style="opacity:.4;pointer-events:none"{% endif %}>Prev</a>
    |
    <a href="{{ url_for('view_pdf', name=name, page=page+1) }}" {% if page>=pages-1 %}style="opacity:.4;pointer-events:none"{% endif %}>Next</a>
  </span>
</div>
<img src="{{ url_for('page_image', name=name, page=page) }}" alt="page">
</body>
"""

def list_pdfs():
    if not FOUNDATIONS_PATH.exists():
        return []
    out = []
    for p in sorted(FOUNDATIONS_PATH.iterdir()):
        if p.is_file() and p.suffix.lower() == ".pdf":
            try:
                doc = fitz.open(p)
                pages = len(doc)
                doc.close()
            except Exception:
                pages = "?"
            out.append({"name": p.name, "pages": pages})
    return out

@app.route("/")
def index():
    pdfs = list_pdfs()
    return render_template_string(INDEX_HTML, pdfs=pdfs)

@app.route("/download/<path:name>")
def download(name):
    safe = FOUNDATIONS_PATH / name
    if not safe.exists() or not safe.is_file():
        abort(404)
    return send_file(str(safe), as_attachment=True)

@app.route("/thumb/<path:name>")
def thumb(name):
    safe = FOUNDATIONS_PATH / name
    if not safe.exists() or not safe.is_file():
        abort(404)
    try:
        doc = fitz.open(safe)
        page = doc.load_page(0)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # resize to fit max width
        w, h = img.size
        if w > THUMB_MAX_W:
            h = int(h * (THUMB_MAX_W / w))
            img = img.resize((THUMB_MAX_W, h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        doc.close()
        return send_file(buf, mimetype="image/png")
    except Exception:
        abort(500)

@app.route("/view/<path:name>")
def view_pdf(name):
    safe = FOUNDATIONS_PATH / name
    if not safe.exists() or not safe.is_file():
        abort(404)
    try:
        doc = fitz.open(safe)
        pages = len(doc)
        doc.close()
    except Exception:
        abort(500)
    page = int(request.args.get("page", 0))
    if page < 0: page = 0
    if page >= pages: page = pages - 1
    return render_template_string(VIEW_HTML, name=name, page=page, pages=pages)

@app.route("/page/<path:name>/<int:page>")
def page_image(name, page):
    safe = FOUNDATIONS_PATH / name
    if not safe.exists() or not safe.is_file():
        abort(404)
    try:
        doc = fitz.open(safe)
        if page < 0 or page >= len(doc):
            doc.close()
            abort(404)
        p = doc.load_page(page)
        mat = fitz.Matrix(2, 2)  # adjust scale factor for quality
        pix = p.get_pixmap(matrix=mat, alpha=False)
        buf = io.BytesIO()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(buf, format="PNG")
        buf.seek(0)
        doc.close()
        return send_file(buf, mimetype="image/png")
    except Exception:
        abort(500)

if __name__ == "__main__":
    # run on 0.0.0.0 so Codespaces port forwarding works
    app.run(host="0.0.0.0", port=5000)
