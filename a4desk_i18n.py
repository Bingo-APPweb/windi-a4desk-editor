#!/usr/bin/env python3
"""
A4 Desk Editor - Multilingual Edition
WINDI Publishing House - Torre de Babel Revertida
DE | EN | PT
"""
import os, json, hashlib, re
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from enum import Enum

app = Flask(__name__)
CORS(app)
DOCUMENTS = {}

class Lang(Enum):
    DE = "de"
    EN = "en"
    PT = "pt"

# Detecção de idioma
PATTERNS = {
    Lang.DE: ['ich', 'sie', 'ist', 'und', 'der', 'die', 'das', 'nicht', 'bitte', 'danke', 'guten', 'dokument', 'hilfe'],
    Lang.PT: ['eu', 'você', 'voce', 'não', 'nao', 'sim', 'como', 'para', 'obrigado', 'olá', 'documento', 'ajuda'],
    Lang.EN: ['the', 'is', 'are', 'have', 'has', 'please', 'thank', 'yes', 'no', 'help', 'document', 'need']
}

def detect_lang(text):
    if not text: return Lang.EN
    words = set(re.findall(r'\b\w+\b', text.lower()))
    scores = {lang: sum(1 for p in pats if p in words) for lang, pats in PATTERNS.items()}
    return max(scores, key=scores.get) if max(scores.values()) > 0 else Lang.EN

# Traduções
T = {
    "title": {Lang.EN: "New Document", Lang.DE: "Neues Dokument", Lang.PT: "Novo Documento"},
    "start": {Lang.EN: "Start writing...", Lang.DE: "Beginnen Sie zu schreiben...", Lang.PT: "Comece a escrever..."},
    "author": {Lang.EN: "Author", Lang.DE: "Autor", Lang.PT: "Autor"},
    "date": {Lang.EN: "Date", Lang.DE: "Datum", Lang.PT: "Data"},
    "reviewer": {Lang.EN: "Reviewer", Lang.DE: "Prüfer", Lang.PT: "Revisor"},
    "save": {Lang.EN: "Save", Lang.DE: "Speichern", Lang.PT: "Salvar"},
    "finalize": {Lang.EN: "Finalize", Lang.DE: "Abschließen", Lang.PT: "Finalizar"},
    "draft": {Lang.EN: "Draft", Lang.DE: "Entwurf", Lang.PT: "Rascunho"},
    "validated": {Lang.EN: "Validated", Lang.DE: "Validiert", Lang.PT: "Validado"},
    "governance": {Lang.EN: "WINDI Governance", Lang.DE: "WINDI Governance", Lang.PT: "Governança WINDI"},
    "principle": {
        Lang.EN: "AI processes. Human decides. WINDI guarantees.",
        Lang.DE: "KI verarbeitet. Der Mensch entscheidet. WINDI garantiert.",
        Lang.PT: "IA processa. Humano decide. WINDI garante."
    },
    "human_only": {Lang.EN: "Human only", Lang.DE: "Nur Mensch", Lang.PT: "Somente humano"},
    "created": {Lang.EN: "Document created", Lang.DE: "Dokument erstellt", Lang.PT: "Documento criado"},
    "saved": {Lang.EN: "Saved and validated", Lang.DE: "Gespeichert und validiert", Lang.PT: "Salvo e validado"},
    "receipt_generated": {Lang.EN: "WINDI-RECEIPT generated!", Lang.DE: "WINDI-RECEIPT erstellt!", Lang.PT: "WINDI-RECEIPT gerado!"},
    "empty_error": {Lang.EN: "Empty content not allowed", Lang.DE: "Leerer Inhalt nicht erlaubt", Lang.PT: "Conteúdo vazio não permitido"},
    "select_lang": {Lang.EN: "Language", Lang.DE: "Sprache", Lang.PT: "Idioma"}
}

def t(key, lang): return T.get(key, {}).get(lang, T.get(key, {}).get(Lang.EN, key))

# G6 Filter multilíngue
G6 = {
    Lang.EN: [("You should ", "Consider: "), ("I recommend ", "Option: "), ("You must ", "Consider: ")],
    Lang.DE: [("Sie sollten ", "Erwägen Sie: "), ("Ich empfehle ", "Option: "), ("Sie müssen ", "Erwägen Sie: ")],
    Lang.PT: [("Você deve ", "Considere: "), ("Recomendo ", "Opção: "), ("Você precisa ", "Considere: ")]
}

def apply_g6(text, lang):
    for old, new in G6.get(lang, G6[Lang.EN]):
        text = text.replace(old, new)
    return text

class Guardrails:
    @staticmethod
    def apply(content, lang):
        text = content.get("text", "")
        violations = []
        guardrails = ["G1", "G2", "G6"]
        if not text.strip():
            violations.append(t("empty_error", lang))
        text = apply_g6(text, lang)
        if violations:
            guardrails.append("G7-BLOCKED")
        return text, guardrails, violations

def make_receipt(doc_id, content, guardrails, lang):
    ts = datetime.now(timezone.utc)
    h = hashlib.sha256(json.dumps(content).encode()).hexdigest()[:12]
    return {
        "receipt_id": f"WINDI-A4DESK-{ts.strftime('%d%b%y').upper()}-{h.upper()}",
        "document_id": doc_id,
        "timestamp": ts.isoformat(),
        "hash": h,
        "guardrails": guardrails,
        "language": lang.value,
        "principle": t("principle", lang)
    }

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "A4 Desk Editor i18n", "languages": ["de", "en", "pt"]})

@app.route('/api/document', methods=['POST'])
def create_doc():
    data = request.json or {}
    lang = Lang(data.get("lang", "en"))
    doc_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    doc = {
        "id": doc_id,
        "title": t("title", lang),
        "content": {"type": "doc", "text": ""},
        "human_fields": {},
        "status": "draft",
        "language": lang.value,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    DOCUMENTS[doc_id] = doc
    return jsonify({"document": doc, "message": t("created", lang)}), 201

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Not found"}), 404
    return jsonify(DOCUMENTS[doc_id])

@app.route('/api/document/<doc_id>', methods=['PUT'])
def update_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Not found"}), 404
    data = request.json
    doc = DOCUMENTS[doc_id]
    text = data.get("content", {}).get("text", "")
    lang = Lang(data.get("lang", doc.get("language", "en")))
    filtered_text, guardrails, violations = Guardrails.apply({"text": text}, lang)
    if violations:
        return jsonify({"error": violations[0], "violations": violations}), 400
    doc["content"] = {"type": "doc", "text": filtered_text}
    doc["human_fields"] = data.get("human_fields", {})
    doc["language"] = lang.value
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"document": doc, "guardrails": guardrails, "message": t("saved", lang)})

@app.route('/api/document/<doc_id>/finalize', methods=['POST'])
def finalize_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Not found"}), 404
    doc = DOCUMENTS[doc_id]
    lang = Lang(doc.get("language", "en"))
    text = doc.get("content", {}).get("text", "")
    _, guardrails, violations = Guardrails.apply({"text": text}, lang)
    if violations:
        return jsonify({"error": violations[0], "violations": violations}), 400
    receipt = make_receipt(doc_id, doc["content"], guardrails, lang)
    doc["status"] = "finalized"
    doc["receipt"] = receipt
    return jsonify({"document": doc, "receipt": receipt, "message": t("receipt_generated", lang)})

@app.route('/api/documents')
def list_docs():
    return jsonify({"documents": list(DOCUMENTS.values())})

@app.route('/api/detect', methods=['POST'])
def detect():
    text = (request.json or {}).get("text", "")
    lang = detect_lang(text)
    return jsonify({"language": lang.value, "text": text})

EDITOR_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A4 Desk - WINDI 🌍</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f7fafc;display:grid;grid-template-columns:240px 1fr 260px;min-height:100vh}
.side{background:#1a365d;color:#fff;padding:20px}
.logo{font-size:1.4rem;font-weight:700;margin-bottom:5px}
.tag{font-size:.7rem;opacity:.8;margin-bottom:15px}
.lang-sel{width:100%;padding:8px;border-radius:6px;border:2px solid #ed8936;margin-bottom:15px;font-size:.9rem}
.btn{width:100%;padding:10px;border:none;border-radius:6px;cursor:pointer;margin-bottom:8px;font-weight:600}
.btn-new{background:#ed8936;color:#fff}
.flags{display:flex;gap:8px;margin-bottom:15px}
.flag{font-size:1.5rem;cursor:pointer;opacity:.5;transition:.2s}
.flag.active,.flag:hover{opacity:1;transform:scale(1.2)}
.main{padding:25px}
.title{font-size:1.5rem;border:none;background:transparent;width:100%;margin-bottom:15px;outline:none}
.editor{background:#fff;border:1px solid #e2e8f0;border-radius:6px;min-height:400px;padding:20px}
#editor{min-height:380px;outline:none}
.panel{background:#fff;border-left:1px solid #e2e8f0;padding:20px}
.panel h3{font-size:.9rem;color:#1a365d;border-bottom:2px solid #ed8936;padding-bottom:8px;margin-bottom:15px}
.field{margin-bottom:12px}
.field label{display:block;font-size:.75rem;font-weight:600;margin-bottom:4px}
.field input{width:100%;padding:8px;border:2px solid #ed8936;border-radius:5px}
.hint{font-size:.65rem;color:#718096}
.status{padding:10px;border-radius:6px;margin-bottom:15px;background:#fef3c7;border-left:3px solid #d97706}
.status.ok{background:#d1fae5;border-left-color:#38a169}
.receipt{background:#f7fafc;padding:10px;border-radius:6px;font-family:monospace;font-size:.75rem;margin-top:10px;display:none}
.btn-save{background:#1a365d;color:#fff}
.btn-final{background:#38a169;color:#fff}
.toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;border-radius:6px;color:#fff;background:#38a169;z-index:99}
.detected{font-size:.7rem;color:#ed8936;margin-top:5px}
</style></head>
<body>
<aside class="side">
<div class="logo">🐉 A4 Desk</div>
<div class="tag" id="principle">AI processes. Human decides. WINDI guarantees.</div>
<div class="flags">
<span class="flag" data-lang="de" onclick="setLang('de')">🇩🇪</span>
<span class="flag active" data-lang="en" onclick="setLang('en')">🇬🇧</span>
<span class="flag" data-lang="pt" onclick="setLang('pt')">🇧🇷</span>
</div>
<button class="btn btn-new" id="btnNew" onclick="newDoc()">+ New Document</button>
<div class="detected" id="detected"></div>
</aside>
<main class="main">
<input class="title" id="docTitle" placeholder="Title">
<div class="editor"><div id="editor" contenteditable="true" oninput="detectText()"></div></div>
</main>
<aside class="panel">
<h3 id="panelTitle">🛡️ WINDI Governance</h3>
<div class="status" id="status"><b>Status:</b> <span id="statusText">Draft</span></div>
<div class="field"><label id="lblAuthor">Author</label><input id="author" placeholder=""><div class="hint" id="hintHuman">🔒 Human only</div></div>
<div class="field"><label id="lblDate">Date</label><input type="date" id="date"></div>
<div class="field"><label id="lblReviewer">Reviewer</label><input id="reviewer" placeholder=""></div>
<button class="btn btn-save" id="btnSave" onclick="saveDoc()">💾 Save</button>
<button class="btn btn-final" id="btnFinal" onclick="finalizeDoc()">✅ Finalize</button>
<div class="receipt" id="receipt"></div>
</aside>
<script>
const TR={
de:{principle:"KI verarbeitet. Der Mensch entscheidet. WINDI garantiert.",newDoc:"+ Neues Dokument",title:"Neues Dokument",start:"Beginnen Sie zu schreiben...",author:"Autor",date:"Datum",reviewer:"Prüfer",save:"💾 Speichern",finalize:"✅ Abschließen",draft:"Entwurf",validated:"Validiert ✓",governance:"🛡️ WINDI Governance",human:"🔒 Nur Mensch",created:"Dokument erstellt",saved:"Gespeichert!",receipt:"WINDI-RECEIPT erstellt!",detected:"Erkannt"},
en:{principle:"AI processes. Human decides. WINDI guarantees.",newDoc:"+ New Document",title:"New Document",start:"Start writing...",author:"Author",date:"Date",reviewer:"Reviewer",save:"💾 Save",finalize:"✅ Finalize",draft:"Draft",validated:"Validated ✓",governance:"🛡️ WINDI Governance",human:"🔒 Human only",created:"Document created",saved:"Saved!",receipt:"WINDI-RECEIPT generated!",detected:"Detected"},
pt:{principle:"IA processa. Humano decide. WINDI garante.",newDoc:"+ Novo Documento",title:"Novo Documento",start:"Comece a escrever...",author:"Autor",date:"Data",reviewer:"Revisor",save:"💾 Salvar",finalize:"✅ Finalizar",draft:"Rascunho",validated:"Validado ✓",governance:"🛡️ Governança WINDI",human:"🔒 Somente humano",created:"Documento criado",saved:"Salvo!",receipt:"WINDI-RECEIPT gerado!",detected:"Detectado"}
};
let lang='en',docId=null;
function setLang(l){
lang=l;
document.querySelectorAll('.flag').forEach(f=>f.classList.toggle('active',f.dataset.lang===l));
document.getElementById('principle').textContent=TR[l].principle;
document.getElementById('btnNew').textContent=TR[l].newDoc;
document.getElementById('lblAuthor').textContent=TR[l].author;
document.getElementById('lblDate').textContent=TR[l].date;
document.getElementById('lblReviewer').textContent=TR[l].reviewer;
document.getElementById('btnSave').textContent=TR[l].save;
document.getElementById('btnFinal').textContent=TR[l].finalize;
document.getElementById('panelTitle').textContent=TR[l].governance;
document.getElementById('hintHuman').textContent=TR[l].human;
document.getElementById('statusText').textContent=TR[l].draft;
}
async function detectText(){
const text=document.getElementById('editor').innerText;
if(text.length>10){
const r=await fetch('/api/detect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
const d=await r.json();
document.getElementById('detected').textContent=TR[lang].detected+': '+d.language.toUpperCase();
}}
async function newDoc(){
const r=await fetch('/api/document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang})});
const d=await r.json();docId=d.document.id;
document.getElementById('docTitle').value=TR[lang].title;
document.getElementById('editor').innerHTML='<p>'+TR[lang].start+'</p>';
document.getElementById('receipt').style.display='none';
document.getElementById('status').className='status';
document.getElementById('statusText').textContent=TR[lang].draft;
toast(TR[lang].created);}
async function saveDoc(){
if(!docId)return;
const content={text:document.getElementById('editor').innerText};
const hf={author:document.getElementById('author').value,date:document.getElementById('date').value,reviewer:document.getElementById('reviewer').value};
const r=await fetch('/api/document/'+docId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content,human_fields:hf,lang})});
if(r.ok){document.getElementById('status').className='status ok';document.getElementById('statusText').textContent=TR[lang].validated;toast(TR[lang].saved);}}
async function finalizeDoc(){
if(!docId)return;await saveDoc();
const r=await fetch('/api/document/'+docId+'/finalize',{method:'POST'});
if(r.ok){const d=await r.json();document.getElementById('receipt').style.display='block';
document.getElementById('receipt').innerHTML='<b>WINDI-RECEIPT</b><br>'+d.receipt.receipt_id+'<br>Hash: '+d.receipt.hash+'<br>🌍 '+d.receipt.language.toUpperCase();
toast(TR[lang].receipt);}}
function toast(msg){const t=document.createElement('div');t.className='toast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),3000);}
newDoc();
</script>
</body></html>'''

@app.route('/')
def index():
    return render_template_string(EDITOR_HTML)

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║   🐉 A4 Desk Editor - Multilingual Edition 🌍                 ║
    ║   "Torre de Babel Revertida"                                  ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║   🇩🇪 Deutsch | 🇬🇧 English | 🇧🇷 Português                      ║
    ║   http://0.0.0.0:8084                                         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=8084, debug=True)
