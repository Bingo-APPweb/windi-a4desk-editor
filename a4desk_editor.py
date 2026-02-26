#!/usr/bin/env python3
"""A4 Desk Editor - WINDI Publishing House"""
import os, json, hashlib
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOCUMENTS = {}
CONFIG = {"ledger_url": "http://127.0.0.1:8081", "port": 8083}

class Guardrails:
    @staticmethod
    def apply(content):
        text = content.get("text", "")
        violations = []
        guardrails = ["G1", "G2", "G6"]
        if not text.strip():
            violations.append("G1: Documento vazio")
        if violations:
            guardrails.append("G7-BLOCKED")
        return guardrails, violations

def make_receipt(doc_id, content, guardrails):
    ts = datetime.now(timezone.utc)
    h = hashlib.sha256(json.dumps(content).encode()).hexdigest()[:12]
    return {
        "receipt_id": f"WINDI-A4DESK-{ts.strftime('%d%b%y').upper()}-{h.upper()}",
        "document_id": doc_id,
        "timestamp": ts.isoformat(),
        "hash": h,
        "guardrails": guardrails
    }

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "A4 Desk Editor", "timestamp": datetime.now(timezone.utc).isoformat()})

@app.route('/api/document', methods=['POST'])
def create_doc():
    doc_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    doc = {
        "id": doc_id,
        "title": (request.json or {}).get("title", "Novo Documento"),
        "content": {"type": "doc", "content": []},
        "human_fields": {},
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    DOCUMENTS[doc_id] = doc
    return jsonify(doc), 201

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Nao encontrado"}), 404
    return jsonify(DOCUMENTS[doc_id])

@app.route('/api/document/<doc_id>', methods=['PUT'])
def update_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Nao encontrado"}), 404
    data = request.json
    doc = DOCUMENTS[doc_id]
    text = data.get("content", {}).get("text", "")
    guardrails, violations = Guardrails.apply({"text": text})
    if violations:
        return jsonify({"error": "Violacao", "violations": violations}), 400
    doc["content"] = data.get("content", doc["content"])
    doc["human_fields"] = data.get("human_fields", {})
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"document": doc, "guardrails": guardrails})

@app.route('/api/document/<doc_id>/finalize', methods=['POST'])
def finalize_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Nao encontrado"}), 404
    doc = DOCUMENTS[doc_id]
    text = doc.get("content", {}).get("text", "")
    guardrails, violations = Guardrails.apply({"text": text})
    if violations:
        return jsonify({"error": "Nao pode finalizar", "violations": violations}), 400
    receipt = make_receipt(doc_id, doc["content"], guardrails)
    doc["status"] = "finalized"
    doc["receipt"] = receipt
    return jsonify({"document": doc, "receipt": receipt})

@app.route('/api/documents')
def list_docs():
    return jsonify({"documents": list(DOCUMENTS.values())})

EDITOR_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A4 Desk - WINDI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f7fafc;display:grid;grid-template-columns:240px 1fr 260px;min-height:100vh}
.side{background:#1a365d;color:#fff;padding:20px}
.logo{font-size:1.4rem;font-weight:700;margin-bottom:5px}
.tag{font-size:.7rem;opacity:.7;margin-bottom:20px}
.btn{width:100%;padding:10px;border:none;border-radius:6px;cursor:pointer;margin-bottom:8px;font-weight:600}
.btn-new{background:#ed8936;color:#fff}
.main{padding:25px}
.title{font-size:1.5rem;border:none;background:transparent;width:100%;margin-bottom:15px;outline:none}
.editor{background:#fff;border:1px solid #e2e8f0;border-radius:6px;min-height:400px;padding:20px}
#editor{min-height:380px;outline:none}
.panel{background:#fff;border-left:1px solid #e2e8f0;padding:20px}
.panel h3{font-size:.9rem;color:#1a365d;border-bottom:2px solid #ed8936;padding-bottom:8px;margin-bottom:15px}
.field{margin-bottom:12px}
.field label{display:block;font-size:.75rem;font-weight:600;margin-bottom:4px}
.field input{width:100%;padding:8px;border:2px solid #ed8936;border-radius:5px}
.status{padding:10px;border-radius:6px;margin-bottom:15px;background:#fef3c7;border-left:3px solid #d97706}
.status.ok{background:#d1fae5;border-left-color:#38a169}
.receipt{background:#f7fafc;padding:10px;border-radius:6px;font-family:monospace;font-size:.75rem;margin-top:10px;display:none}
.btn-save{background:#1a365d;color:#fff}
.btn-final{background:#38a169;color:#fff}
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:6px;color:#fff;background:#38a169}
</style></head>
<body>
<aside class="side">
<div class="logo">🐉 A4 Desk</div>
<div class="tag">AI processes. Human decides. WINDI guarantees.</div>
<button class="btn btn-new" onclick="newDoc()">+ Novo Documento</button>
</aside>
<main class="main">
<input class="title" id="title" value="Novo Documento" placeholder="Titulo">
<div class="editor"><div id="editor" contenteditable="true"><p>Comece a escrever...</p></div></div>
</main>
<aside class="panel">
<h3>🛡️ Governanca WINDI</h3>
<div class="status" id="status"><b>Status:</b> Rascunho</div>
<div class="field"><label>Autor</label><input id="author" placeholder="Seu nome"></div>
<div class="field"><label>Data</label><input type="date" id="date"></div>
<div class="field"><label>Revisor</label><input id="reviewer" placeholder="Revisor"></div>
<button class="btn btn-save" onclick="saveDoc()">💾 Salvar</button>
<button class="btn btn-final" onclick="finalizeDoc()">✅ Finalizar</button>
<div class="receipt" id="receipt"></div>
</aside>
<script>
let docId=null;
async function newDoc(){
const r=await fetch('/api/document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Novo Documento'})});
const d=await r.json();docId=d.id;document.getElementById('title').value=d.title;
document.getElementById('editor').innerHTML='<p>Comece a escrever...</p>';
document.getElementById('receipt').style.display='none';
document.getElementById('status').className='status';
document.getElementById('status').innerHTML='<b>Status:</b> Rascunho';}
async function saveDoc(){
if(!docId)return alert('Crie um documento');
const content={text:document.getElementById('editor').innerText};
const hf={author:document.getElementById('author').value,date:document.getElementById('date').value,reviewer:document.getElementById('reviewer').value};
const r=await fetch('/api/document/'+docId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content,human_fields:hf})});
if(r.ok){document.getElementById('status').className='status ok';document.getElementById('status').innerHTML='<b>Status:</b> Validado ✓';}}
async function finalizeDoc(){
if(!docId)return alert('Crie um documento');await saveDoc();
const r=await fetch('/api/document/'+docId+'/finalize',{method:'POST'});
if(r.ok){const d=await r.json();document.getElementById('receipt').style.display='block';
document.getElementById('receipt').innerHTML='<b>WINDI-RECEIPT</b><br>'+d.receipt.receipt_id+'<br>Hash: '+d.receipt.hash;}}
newDoc();
</script>
</body></html>'''

@app.route('/')
def index():
    return render_template_string(EDITOR_HTML)

if __name__ == '__main__':
    print("🐉 A4 Desk Editor rodando em http://0.0.0.0:8083")
    app.run(host='0.0.0.0', port=8083, debug=True)
