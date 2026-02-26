#!/usr/bin/env python3
"""
A4 Desk Editor - Universal Edition
WINDI Publishing House - Torre de Babel Revertida
Auto-detect browser language + External JSON translations + Community contributions
"""
import os, json, hashlib, re
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DOCUMENTS = {}
TRANSLATIONS = {}

# Load translations from JSON file
def load_translations():
    global TRANSLATIONS
    try:
        path = os.path.join(os.path.dirname(__file__), 'translations.json')
        with open(path, 'r', encoding='utf-8') as f:
            TRANSLATIONS = json.load(f)
        print(f"✓ Loaded {len(TRANSLATIONS)-1} languages")
    except Exception as e:
        print(f"✗ Translation error: {e}")
        TRANSLATIONS = {"en": {"lang_name": "English", "flag": "🇬🇧", "principle": "AI processes. Human decides. WINDI guarantees."}}

load_translations()

def get_langs():
    """Get available languages (exclude _meta)"""
    return {k: v for k, v in TRANSLATIONS.items() if not k.startswith('_')}

def t(key, lang):
    """Translate with fallback to English"""
    langs = get_langs()
    if lang in langs and key in langs[lang]:
        return langs[lang][key]
    if 'en' in langs and key in langs['en']:
        return langs['en'][key]
    return key

def detect_browser_lang(accept_lang):
    """Detect language from Accept-Language header"""
    if not accept_lang:
        return 'en'
    langs = get_langs()
    for part in accept_lang.split(','):
        code = part.split(';')[0].strip().lower()[:2]
        if code in langs:
            return code
    return 'en'

def detect_text_lang(text):
    """Detect language from text content"""
    if not text or len(text) < 10:
        return None
    patterns = {
        'de': ['ich', 'sie', 'ist', 'und', 'der', 'die', 'das', 'nicht', 'bitte', 'haben', 'werden'],
        'pt': ['você', 'voce', 'não', 'nao', 'para', 'como', 'está', 'esta', 'obrigado', 'preciso'],
        'es': ['está', 'esta', 'pero', 'para', 'como', 'tiene', 'puede', 'hola', 'gracias', 'necesito'],
        'fr': ['vous', 'nous', 'pour', 'dans', 'avec', 'cette', 'sont', 'bonjour', 'merci', 'besoin'],
        'it': ['sono', 'essere', 'questo', 'questa', 'hanno', 'come', 'ciao', 'grazie', 'bisogno'],
        'nl': ['het', 'een', 'zijn', 'hebben', 'voor', 'niet', 'hallo', 'dank', 'nodig'],
        'pl': ['jest', 'nie', 'tak', 'jak', 'dla', 'czy', 'cześć', 'dziękuję', 'potrzebuję'],
        'en': ['the', 'is', 'are', 'have', 'has', 'for', 'with', 'this', 'that', 'hello', 'need']
    }
    words = set(re.findall(r'\b\w+\b', text.lower()))
    scores = {lang: sum(1 for p in pats if p in words) for lang, pats in patterns.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'en'

# G6 patterns per language
G6_PATTERNS = {
    'en': [("You should ", "Consider: "), ("I recommend ", "Option: "), ("You must ", "Consider: ")],
    'de': [("Sie sollten ", "Erwägen Sie: "), ("Ich empfehle ", "Option: "), ("Sie müssen ", "Erwägen Sie: ")],
    'pt': [("Você deve ", "Considere: "), ("Recomendo ", "Opção: "), ("Você precisa ", "Considere: ")],
    'es': [("Usted debe ", "Considere: "), ("Recomiendo ", "Opción: "), ("Debe ", "Considere: ")],
    'fr': [("Vous devez ", "Considérez: "), ("Je recommande ", "Option: "), ("Il faut ", "Considérez: ")],
    'it': [("Dovresti ", "Considera: "), ("Raccomando ", "Opzione: "), ("Devi ", "Considera: ")],
    'nl': [("U moet ", "Overweeg: "), ("Ik raad aan ", "Optie: "), ("Je moet ", "Overweeg: ")],
    'pl': [("Powinieneś ", "Rozważ: "), ("Polecam ", "Opcja: "), ("Musisz ", "Rozważ: ")]
}

def apply_g6(text, lang):
    patterns = G6_PATTERNS.get(lang, G6_PATTERNS.get('en', []))
    for old, new in patterns:
        text = text.replace(old, new)
    return text

def make_receipt(doc_id, content, guardrails, lang):
    ts = datetime.now(timezone.utc)
    h = hashlib.sha256(json.dumps(content).encode()).hexdigest()[:12]
    return {
        "receipt_id": f"WINDI-A4DESK-{ts.strftime('%d%b%y').upper()}-{h.upper()}",
        "document_id": doc_id,
        "timestamp": ts.isoformat(),
        "hash": h,
        "guardrails": guardrails,
        "language": lang,
        "principle": t("principle", lang)
    }

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "A4 Desk Universal", "languages": list(get_langs().keys())})

@app.route('/api/languages')
def languages():
    """Return all available languages"""
    langs = get_langs()
    return jsonify({code: {"name": data.get("lang_name", code), "flag": data.get("flag", "🌍")} for code, data in langs.items()})

@app.route('/api/translations')
def translations():
    """Return full translations (for community contributions)"""
    return jsonify(TRANSLATIONS)

@app.route('/api/translations/reload', methods=['POST'])
def reload_translations():
    """Hot-reload translations without restart"""
    load_translations()
    return jsonify({"status": "reloaded", "languages": list(get_langs().keys())})

@app.route('/api/detect', methods=['POST'])
def detect():
    text = (request.json or {}).get("text", "")
    lang = detect_text_lang(text)
    return jsonify({"language": lang, "name": t("lang_name", lang), "flag": t("flag", lang)})

@app.route('/api/document', methods=['POST'])
def create_doc():
    data = request.json or {}
    lang = data.get("lang", detect_browser_lang(request.headers.get('Accept-Language')))
    doc_id = f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    doc = {
        "id": doc_id,
        "title": t("title", lang),
        "content": {"type": "doc", "text": ""},
        "human_fields": {},
        "status": "draft",
        "language": lang,
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
    lang = data.get("lang", doc.get("language", "en"))
    text = data.get("content", {}).get("text", "")
    text = apply_g6(text, lang)
    guardrails = ["G1", "G2", "G6"]
    if not text.strip():
        return jsonify({"error": t("empty_error", lang) if "empty_error" in get_langs().get(lang, {}) else "Empty not allowed"}), 400
    doc["content"] = {"type": "doc", "text": text}
    doc["human_fields"] = data.get("human_fields", {})
    doc["language"] = lang
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return jsonify({"document": doc, "guardrails": guardrails, "message": t("saved", lang)})

@app.route('/api/document/<doc_id>/finalize', methods=['POST'])
def finalize_doc(doc_id):
    if doc_id not in DOCUMENTS:
        return jsonify({"error": "Not found"}), 404
    doc = DOCUMENTS[doc_id]
    lang = doc.get("language", "en")
    text = doc.get("content", {}).get("text", "")
    if not text.strip():
        return jsonify({"error": "Cannot finalize empty"}), 400
    guardrails = ["G1", "G2", "G6", "G7", "G8"]
    receipt = make_receipt(doc_id, doc["content"], guardrails, lang)
    doc["status"] = "finalized"
    doc["receipt"] = receipt
    return jsonify({"document": doc, "receipt": receipt, "message": t("receipt_gen", lang)})

@app.route('/api/documents')
def list_docs():
    return jsonify({"documents": list(DOCUMENTS.values())})


EDITOR_HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A4 Desk - WINDI Universal 🌍</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f7fafc;display:grid;grid-template-columns:260px 1fr 280px;min-height:100vh}
.side{background:#1a365d;color:#fff;padding:20px}
.logo{font-size:1.4rem;font-weight:700;margin-bottom:5px}
.tag{font-size:.7rem;opacity:.8;margin-bottom:15px;min-height:2.5em}
.flags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:15px;padding:10px;background:rgba(255,255,255,.1);border-radius:8px}
.flag{font-size:1.3rem;cursor:pointer;opacity:.5;transition:.2s;padding:4px}
.flag:hover{opacity:.8;transform:scale(1.1)}
.flag.active{opacity:1;transform:scale(1.2);background:rgba(255,255,255,.2);border-radius:4px}
.btn{width:100%;padding:10px;border:none;border-radius:6px;cursor:pointer;margin-bottom:8px;font-weight:600}
.btn-new{background:#ed8936;color:#fff}
.detected{font-size:.7rem;color:#ed8936;margin-top:8px;padding:8px;background:rgba(255,255,255,.1);border-radius:4px}
.lang-count{font-size:.65rem;opacity:.6;margin-bottom:10px}
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
.babel{font-size:.6rem;opacity:.5;margin-top:15px;text-align:center}
</style></head>
<body>
<aside class="side">
<div class="logo">🐉 A4 Desk</div>
<div class="tag" id="principle"></div>
<div class="lang-count" id="langCount"></div>
<div class="flags" id="flags"></div>
<button class="btn btn-new" id="btnNew" onclick="newDoc()"></button>
<div class="detected" id="detected"></div>
<div class="babel">🗼 Torre de Babel Revertida<br>Community Translations Welcome</div>
</aside>
<main class="main">
<input class="title" id="docTitle" placeholder="">
<div class="editor"><div id="editor" contenteditable="true" oninput="onType()"></div></div>
</main>
<aside class="panel">
<h3 id="panelTitle"></h3>
<div class="status" id="status"><b id="lblStatus"></b> <span id="statusText"></span></div>
<div class="field"><label id="lblAuthor"></label><input id="author"><div class="hint" id="hintHuman"></div></div>
<div class="field"><label id="lblDate"></label><input type="date" id="date"></div>
<div class="field"><label id="lblReviewer"></label><input id="reviewer"></div>
<button class="btn btn-save" id="btnSave" onclick="saveDoc()"></button>
<button class="btn btn-final" id="btnFinal" onclick="finalizeDoc()"></button>
<div class="receipt" id="receipt"></div>
</aside>
<script>
let TR={},lang='en',docId=null,langs={};

async function init(){
const r=await fetch('/api/languages');
langs=await r.json();
const r2=await fetch('/api/translations');
TR=await r2.json();
delete TR._meta;
renderFlags();
lang=detectBrowserLang();
setLang(lang);
newDoc();
document.getElementById('langCount').textContent=Object.keys(langs).length+' languages available';}

function detectBrowserLang(){
const nav=navigator.language||navigator.userLanguage||'en';
const code=nav.slice(0,2).toLowerCase();
return langs[code]?code:'en';}

function renderFlags(){
const el=document.getElementById('flags');
el.innerHTML='';
for(const[code,data]of Object.entries(langs)){
const span=document.createElement('span');
span.className='flag';
span.dataset.lang=code;
span.textContent=data.flag;
span.title=data.name;
span.onclick=()=>setLang(code);
el.appendChild(span);}}

function setLang(l){
lang=l;
document.querySelectorAll('.flag').forEach(f=>f.classList.toggle('active',f.dataset.lang===l));
const T=TR[l]||TR.en;
document.getElementById('principle').textContent=T.principle||'';
document.getElementById('btnNew').textContent=T.new_doc||'+ New';
document.getElementById('lblAuthor').textContent=T.author||'Author';
document.getElementById('lblDate').textContent=T.date||'Date';
document.getElementById('lblReviewer').textContent=T.reviewer||'Reviewer';
document.getElementById('btnSave').textContent='💾 '+(T.save||'Save');
document.getElementById('btnFinal').textContent='✅ '+(T.finalize||'Finalize');
document.getElementById('panelTitle').textContent='🛡️ '+(T.governance||'Governance');
document.getElementById('hintHuman').textContent='🔒 '+(T.human_only||'Human only');
document.getElementById('lblStatus').textContent=(T.status||'Status')+':';
document.getElementById('statusText').textContent=T.draft||'Draft';
document.getElementById('docTitle').placeholder=T.title||'Title';}

let typeTimer;
function onType(){
clearTimeout(typeTimer);
typeTimer=setTimeout(detectText,500);}

async function detectText(){
const text=document.getElementById('editor').innerText;
if(text.length<10)return;
const r=await fetch('/api/detect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
const d=await r.json();
const T=TR[lang]||TR.en;
document.getElementById('detected').innerHTML=(T.detected||'Detected')+': <b>'+d.flag+' '+d.name+'</b>';}

async function newDoc(){
const r=await fetch('/api/document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang})});
const d=await r.json();docId=d.document.id;
const T=TR[lang]||TR.en;
document.getElementById('docTitle').value=T.title||'New Document';
document.getElementById('editor').innerHTML='<p>'+(T.start||'Start writing...')+'</p>';
document.getElementById('receipt').style.display='none';
document.getElementById('status').className='status';
document.getElementById('statusText').textContent=T.draft||'Draft';
document.getElementById('detected').innerHTML='';
toast(T.created||'Created');}

async function saveDoc(){
if(!docId)return;
const content={text:document.getElementById('editor').innerText};
const hf={author:document.getElementById('author').value,date:document.getElementById('date').value,reviewer:document.getElementById('reviewer').value};
const r=await fetch('/api/document/'+docId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content,human_fields:hf,lang})});
const T=TR[lang]||TR.en;
if(r.ok){document.getElementById('status').className='status ok';document.getElementById('statusText').textContent=(T.validated||'Validated')+' ✓';toast(T.saved||'Saved!');}}

async function finalizeDoc(){
if(!docId)return;await saveDoc();
const r=await fetch('/api/document/'+docId+'/finalize',{method:'POST'});
const T=TR[lang]||TR.en;
if(r.ok){const d=await r.json();document.getElementById('receipt').style.display='block';
document.getElementById('receipt').innerHTML='<b>WINDI-RECEIPT</b><br>'+d.receipt.receipt_id+'<br>Hash: '+d.receipt.hash+'<br>🌍 '+d.receipt.language.toUpperCase()+'<br><small>'+d.receipt.principle+'</small>';
toast(T.receipt_gen||'Receipt generated!');}}

function toast(msg){const t=document.createElement('div');t.className='toast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),3000);}

init();
</script>
</body></html>'''

@app.route('/')
def index():
    return render_template_string(EDITOR_HTML)

if __name__ == '__main__':
    langs = list(get_langs().keys())
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║   🐉 A4 Desk Editor - UNIVERSAL Edition 🌍                    ║
    ║   "Torre de Babel Revertida"                                  ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║   Languages: {', '.join(langs):<43} ║
    ║   Auto-detect: Browser + Text                                 ║
    ║   Community: translations.json                                ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║   http://0.0.0.0:8085                                         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=8085, debug=True)
