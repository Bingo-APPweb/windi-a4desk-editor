#!/usr/bin/env python3
"""
A4 Desk BABEL - Tiptap Edition v4.7-gov
WINDI Publishing House - Torre de Babel Revertida
VERSION 4.3 - 29 JAN 2026

CHANGELOG v4.7-gov:
- Mein Profil: Modal para editar dados do usuário
- Preview antes de Einfügen
- Human Authorship Notice no PDF
"""
import os
import sys
import json
import hashlib
import sqlite3
import subprocess
import tempfile
import base64
import secrets
from io import BytesIO
import qrcode
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/opt/windi")  # Sandbox Core engine
# WINDI v0.1 Integrity Layer
try:
    from engine.windi_c14n import (
        build_windi_envelope, 
        verify_envelope_integrity,
        sha256_hex
    )
    WINDI_C14N_AVAILABLE = True
    print("✓ WINDI C14N loaded")
except Exception as e:
    WINDI_C14N_AVAILABLE = False
    print(f"⚠ WINDI C14N not available: {e}")

# WINDI v0.1 Config
WINDI_ISSUER_ID = os.environ.get('WINDI_ISSUER_ID', 'windi.publishing.de')
WINDI_ISSUER_SECRET = os.environ.get('WINDI_ISSUER_SECRET', 'change_in_production').encode('utf-8')
WINDI_POLICY_REF = os.environ.get('WINDI_POLICY_REF', 'eu.ai.act.article.52')
WINDI_JURISDICTIONS = ['DE', 'EU']

# WINDI Print Watermark Layer v0.1
try:
    from engine.windi_print_layer import embed_print_watermark
    WINDI_PRINT_LAYER_AVAILABLE = True
    print("✓ WINDI Print Layer loaded")
except Exception as e:
    WINDI_PRINT_LAYER_AVAILABLE = False
    print(f"⚠ WINDI Print Layer not available: {e}")
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_file, render_template_string, send_from_directory, session

sys.path.insert(0, "/opt/windi/a4desk-editor/intent_parser")
try:
    from chat_integration import ChatIntentHandler
    INTENT_HANDLER = ChatIntentHandler()
    INTENT_PARSER_AVAILABLE = True
    print("✓ Intent Parser loaded")
except Exception as e:
    INTENT_PARSER_AVAILABLE = False
    print(f"⚠ Intent Parser not available: {e}")

# Phase 4: ISP Resolver
sys.path.insert(0, '/opt/windi/windi_agent/institutional_profiles')
try:
    from resolver import resolve_institutional_style
    ISP_RESOLVER_AVAILABLE = True
    print("✓ ISP Resolver loaded")
except Exception as e:
    ISP_RESOLVER_AVAILABLE = False
    print(f"⚠ ISP Resolver not available: {e}")

sys.path.insert(0, '/opt/windi/template_registry')

from dotenv import load_dotenv
load_dotenv('/etc/windi/secrets.env')

try:
    from api_endpoints import register_registry_endpoints
    from isp_endpoints import isp_bp
    from isp_loader import load_profile, load_css, get_logo_path
    REGISTRY_AVAILABLE = True
except ImportError as e:
    REGISTRY_AVAILABLE = False
    print(f"⚠️ Template Registry não disponível: {e}")

from flask_cors import CORS
import requests
from weasyprint import HTML as WeasyHTML

sys.path.insert(0, '/opt/windi/templates')
try:
    from bescheid_generator import generate_bescheid_pdf, BEISPIEL_BAUGENEHMIGUNG
    BESCHEID_AVAILABLE = True
except ImportError:
    BESCHEID_AVAILABLE = False

# ─── WINDI DeepDOCFakes — Document Security Division ─────────
sys.path.insert(0, '/opt/windi/engine')
try:
    from deepdocfakes import compute_structural_hash, compute_resilience_score, resilience_rating
    from deepdocfakes.provenance_engine import build_provenance_record, persist_provenance_record
    from deepdocfakes.verify_engine import verify_by_submission_id, VerificationStatus
    DEEPDOCFAKES_AVAILABLE = True
    print("✅ DeepDOCFakes Document Security Division loaded")
except ImportError as e:
    DEEPDOCFAKES_AVAILABLE = False
    print(f"⚠️ DeepDOCFakes not available: {e}")

app = Flask(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.secret_key = os.getenv('WINDI_SECRET_KEY', secrets.token_hex(32))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('/opt/windi/a4desk-editor/static', filename)

if REGISTRY_AVAILABLE:
    register_registry_endpoints(app)
    app.register_blueprint(isp_bp)
CORS(app)

CONFIG = {
    "port": int(os.getenv("WINDI_BABEL_PORT", 8085)),
    "actor": "a4desk-babel-tiptap",
    "domain": "document-production",
    "trust_bus": "http://127.0.0.1:8081",
    "gateway": "http://127.0.0.1:8082",
    "db_path": "/opt/windi/data/babel_documents.db",
    "session_timeout_minutes": 10,
    "session_max_hours": 8,
    "max_login_attempts": 3
}

SESSIONS = {}

def create_session(user_data):
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    SESSIONS[session_id] = {
        "user_id": user_data.get("employee_id", ""),
        "full_name": user_data.get("full_name", ""),
        "department": user_data.get("department", ""),
        "position": user_data.get("position", ""),
        "email": user_data.get("email", ""),
        "created_at": now.isoformat(),
        "last_activity": now.isoformat(),
        "expires_at": (now + timedelta(hours=CONFIG["session_max_hours"])).isoformat(),
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", ""),
        "reauth_count": 0,
        "actions_count": 0
    }
    return session_id

def validate_session(session_id):
    if not session_id or session_id not in SESSIONS:
        return None
    sess = SESSIONS[session_id]
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(sess["expires_at"].replace('Z', '+00:00'))
    if now > expires_at:
        del SESSIONS[session_id]
        return None
    last_activity = datetime.fromisoformat(sess["last_activity"].replace('Z', '+00:00'))
    if (now - last_activity).total_seconds() > CONFIG["session_timeout_minutes"] * 60:
        del SESSIONS[session_id]
        return None
    sess["last_activity"] = now.isoformat()
    sess["actions_count"] += 1
    return sess

def invalidate_session(session_id):
    if session_id in SESSIONS:
        del SESSIONS[session_id]
        return True
    return False

def init_db():
    os.makedirs(os.path.dirname(CONFIG["db_path"]), exist_ok=True)
    conn = sqlite3.connect(CONFIG["db_path"])
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, title TEXT, content TEXT, content_html TEXT,
            human_fields TEXT, status TEXT DEFAULT 'draft', language TEXT DEFAULT 'de',
            receipt TEXT, user_id TEXT DEFAULT 'anonymous', created_by TEXT DEFAULT '',
            modified_by TEXT DEFAULT '', witness TEXT DEFAULT '', dragon TEXT DEFAULT 'claude',
            created_at TEXT, updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS human_identities (
            id TEXT PRIMARY KEY, full_name TEXT NOT NULL, employee_id TEXT UNIQUE NOT NULL,
            department TEXT, position TEXT, email TEXT, supervisor_id TEXT, supervisor_name TEXT,
            password_hash TEXT, failed_attempts INTEGER DEFAULT 0, locked_until TEXT,
            created_at TEXT, updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT, session_id TEXT,
            action TEXT NOT NULL, actor_id TEXT NOT NULL, actor_name TEXT NOT NULL,
            actor_employee_id TEXT, actor_position TEXT, witness_id TEXT, witness_name TEXT,
            witness_position TEXT, old_status TEXT, new_status TEXT, content_hash TEXT,
            timestamp TEXT NOT NULL, ip_address TEXT, user_agent TEXT, notes TEXT,
            previous_hash TEXT, current_hash TEXT
        )
    """)
    for m in ["ALTER TABLE documents ADD COLUMN user_id TEXT DEFAULT 'anonymous'",
              "ALTER TABLE documents ADD COLUMN created_by TEXT DEFAULT ''",
              "ALTER TABLE documents ADD COLUMN modified_by TEXT DEFAULT ''",
              "ALTER TABLE documents ADD COLUMN witness TEXT DEFAULT ''",
              "ALTER TABLE documents ADD COLUMN dragon TEXT DEFAULT 'claude'",
              "ALTER TABLE documents ADD COLUMN content_html TEXT DEFAULT ''"]:
        try: cursor.execute(m)
        except: pass
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_db():
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.row_factory = sqlite3.Row
    return conn

init_db()

def get_last_audit_hash():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT current_hash FROM document_audit ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["current_hash"] if row else "GENESIS"

def log_audit(doc_id, action, actor_data, session_id=None, witness_data=None, old_status=None, new_status=None, content_hash=None, notes=None):
    conn = get_db()
    cursor = conn.cursor()
    previous_hash = get_last_audit_hash()
    timestamp = datetime.now(timezone.utc).isoformat()
    hash_input = f"{doc_id}{action}{actor_data.get('id','')}{timestamp}{previous_hash}"
    current_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    cursor.execute("""
        INSERT INTO document_audit (document_id, session_id, action, actor_id, actor_name, actor_employee_id, actor_position,
         witness_id, witness_name, witness_position, old_status, new_status, content_hash, timestamp, ip_address, user_agent, notes, previous_hash, current_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, session_id, action, actor_data.get('id', 'unknown'), actor_data.get('name', 'Anonymous'), actor_data.get('employee_id', ''), actor_data.get('position', ''),
          witness_data.get('id', '') if witness_data else '', witness_data.get('name', '') if witness_data else '', witness_data.get('position', '') if witness_data else '',
          old_status, new_status, content_hash, timestamp, request.remote_addr if request else '', request.headers.get('User-Agent', '') if request else '', notes, previous_hash, current_hash))
    conn.commit()
    conn.close()
    return current_hash

def create_migration_audit(doc_id, doc_data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM document_audit WHERE document_id = ?", (doc_id,))
    if cursor.fetchone()['count'] > 0:
        conn.close()
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    previous_hash = get_last_audit_hash()
    hash_input = f"{doc_id}LEGACY_MIGRATED{timestamp}{previous_hash}"
    current_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    cursor.execute("""INSERT INTO document_audit (document_id, action, actor_id, actor_name, actor_employee_id, old_status, new_status, timestamp, notes, previous_hash, current_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (doc_id, 'LEGACY_MIGRATED', doc_data.get('user_id', 'unknown'), doc_data.get('created_by', 'Unknown (Pre-v4)'), '', None, doc_data.get('status', 'draft'), doc_data.get('created_at', timestamp), f'Dokument migriert von v3', previous_hash, current_hash))
    conn.commit()
    conn.close()

def save_human_identity(identity_data):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    identity_id = identity_data.get('id') or f"HID-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    password_hash = hashlib.sha256(identity_data['password'].encode()).hexdigest() if identity_data.get('password') else None
    cursor.execute("""INSERT OR REPLACE INTO human_identities (id, full_name, employee_id, department, position, email, supervisor_id, supervisor_name, password_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, (SELECT password_hash FROM human_identities WHERE id = ?)), COALESCE((SELECT created_at FROM human_identities WHERE id = ?), ?), ?)""",
        (identity_id, identity_data.get('full_name', ''), identity_data.get('employee_id', ''), identity_data.get('department', ''), identity_data.get('position', ''), identity_data.get('email', ''), identity_data.get('supervisor_id', ''), identity_data.get('supervisor_name', ''), password_hash, identity_id, identity_id, now, now))
    conn.commit()
    conn.close()
    return identity_id

def get_human_identity(employee_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM human_identities WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def verify_identity(employee_id, password):
    identity = get_human_identity(employee_id)
    if not identity:
        return False, "Mitarbeiter nicht gefunden"
    if identity.get('locked_until'):
        locked_until = datetime.fromisoformat(identity['locked_until'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) < locked_until:
            return False, "Konto gesperrt"
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if identity.get('password_hash') != password_hash:
        conn = get_db()
        cursor = conn.cursor()
        new_attempts = (identity.get('failed_attempts', 0) or 0) + 1
        if new_attempts >= CONFIG["max_login_attempts"]:
            locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            cursor.execute("UPDATE human_identities SET failed_attempts = ?, locked_until = ? WHERE employee_id = ?", (new_attempts, locked_until, employee_id))
        else:
            cursor.execute("UPDATE human_identities SET failed_attempts = ? WHERE employee_id = ?", (new_attempts, employee_id))
        conn.commit()
        conn.close()
        return False, f"Falsches Passwort. Versuch {new_attempts}/{CONFIG['max_login_attempts']}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE human_identities SET failed_attempts = 0, locked_until = NULL WHERE employee_id = ?", (employee_id,))
    conn.commit()
    conn.close()
    return True, identity

@app.route('/api/migrate/claim-documents', methods=['POST'])
def claim_legacy_documents():
    data = request.json or {}
    old_user_id, new_employee_id, new_user_name = data.get('old_user_id', ''), data.get('new_employee_id', ''), data.get('new_user_name', '')
    if not old_user_id or not new_employee_id or old_user_id == new_employee_id:
        return jsonify({"migrated": 0})
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM documents WHERE user_id = ?", (old_user_id,))
    count = cursor.fetchone()['count']
    if count == 0:
        conn.close()
        return jsonify({"migrated": 0})
    cursor.execute("SELECT * FROM documents WHERE user_id = ?", (old_user_id,))
    docs = cursor.fetchall()
    cursor.execute("UPDATE documents SET user_id = ?, modified_by = ? WHERE user_id = ?", (new_employee_id, f'MIGRATION von {old_user_id}', old_user_id))
    conn.commit()
    conn.close()
    for doc in docs:
        create_migration_audit(doc['id'], dict(doc))
    log_audit('SYSTEM', 'DOCS_MIGRATED', {'id': new_employee_id, 'name': new_user_name, 'employee_id': new_employee_id}, notes=f'{count} Dokumente migriert')
    return jsonify({"migrated": count, "message": f"{count} Dokumente migriert"})

TRANSLATIONS = {
    "de": {"principle": "KI verarbeitet. Der Mensch entscheidet. WINDI garantiert.", "title": "Neues Dokument", "draft": "Entwurf", "validated": "Validiert", "finalized": "Abgeschlossen", "witness_required": "Prüfer erforderlich"},
    "en": {"principle": "AI processes. Human decides. WINDI guarantees.", "title": "New Document", "draft": "Draft", "validated": "Validated", "finalized": "Finalized", "witness_required": "Witness required"},
    "pt": {"principle": "IA processa. Humano decide. WINDI garante.", "title": "Novo Documento", "draft": "Rascunho", "validated": "Validado", "finalized": "Finalizado", "witness_required": "Testemunha necessária"}
}

def t(key, lang):
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS.get('de', {}).get(key) or key

def make_receipt(doc_id, content, lang, author_data=None, witness_data=None):
    ts = datetime.now(timezone.utc)
    h = hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()[:12]
    receipt = {"receipt_id": f"WINDI-BABEL-{ts.strftime('%d%b%y').upper()}-{h.upper()}", "document_id": doc_id, "timestamp": ts.isoformat(), "hash": h, "guardrails": ["G1", "G2", "G6", "G7", "G8"], "language": lang, "principle": t("principle", lang)}
    if author_data:
        receipt["author"] = {"name": author_data.get('name', ''), "employee_id": author_data.get('employee_id', ''), "position": author_data.get('position', '')}
    if witness_data:
        receipt["witness"] = {"name": witness_data.get('name', ''), "employee_id": witness_data.get('id', ''), "position": witness_data.get('position', ''), "relation": witness_data.get('relation', '')}
    # ─── DeepDOCFakes: Structural Hash + Resilience Score ─────
    if DEEPDOCFAKES_AVAILABLE:
        try:
            gov_level = "HIGH"  # default; can be overridden by ISP profile
            decision_payload = {
                "submission_id": receipt["receipt_id"],
                "governance_level": gov_level,
                "policy_version": "2.2.0",
                "isp_profile": "windi_default",
                "organization": "WINDI Publishing House",
                "metadata": {"document_id": doc_id, "language": lang}
            }
            struct_hash = compute_structural_hash(decision_payload)
            score = compute_resilience_score(gov_level, {"provenance_record": "required", "registry": True, "structural_hash": "strict", "embed_pdf_metadata": True, "identity_governance": True, "forensic_ledger": True, "four_eyes": True, "jurisdiction_bound": True, "tamper_evidence": True})
            rating = resilience_rating(score)
            receipt["structural_hash"] = struct_hash[:16]
            receipt["resilience_score"] = score
            receipt["resilience_rating"] = rating
            receipt["sof_protocol"] = "WINDI-SOF-v1"
        except Exception as e:
            print(f"[WINDI] DeepDOCFakes receipt enrichment error: {e}")
    return receipt

def generate_qr_base64(data):
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "A4 Desk BABEL v4.7-gov", "version": "4.6", "compliance": ["EU AI Act", "BSI", "DSGVO"]})

def generate_windi_envelope(doc_id, content_bytes, content_type, author_data, intent_code="publish.document"):
    """Generate a WINDI v0.1 envelope for document integrity."""
    if not WINDI_C14N_AVAILABLE:
        return None
    try:
        version = "v1"
        responsible_actor = author_data.get('employee_id', 'unknown')
        if author_data.get('full_name'):
            responsible_actor = f"{responsible_actor}:{author_data['full_name']}"
        envelope = build_windi_envelope(
            document_id=doc_id,
            version_id=version,
            content_type=content_type,
            body_bytes=content_bytes,
            issuer_id=WINDI_ISSUER_ID,
            responsible_actor_id=responsible_actor,
            intent_code=intent_code,
            policy_reference=WINDI_POLICY_REF,
            issuer_secret=WINDI_ISSUER_SECRET,
            jurisdictions=WINDI_JURISDICTIONS
        )
        return envelope
    except Exception as e:
        print(f"[WINDI] Envelope error: {e}", flush=True)
        return None

def save_windi_envelope(doc_id, envelope):
    """Save WINDI envelope to filesystem."""
    if not envelope:
        return None
    try:
        envelope_dir = Path("/opt/windi/data/envelopes")
        envelope_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = envelope_dir / f"{doc_id}.envelope.json"
        with open(envelope_path, 'w', encoding='utf-8') as f:
            json.dump(envelope, f, indent=2, ensure_ascii=False)
        print(f"[WINDI] Envelope saved: {doc_id}")
        return str(envelope_path)
    except Exception as e:
        print(f"[WINDI] Save error: {e}")
        return None

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json or {}
    employee_id, password = data.get('employee_id', ''), data.get('password', '')
    provided_name = data.get('full_name', '').strip()
    identity = get_human_identity(employee_id)
    if not identity:
        save_human_identity({'employee_id': employee_id, 'full_name': provided_name, 'department': data.get('department', ''), 'position': data.get('position', ''), 'email': data.get('email', ''), 'supervisor_id': data.get('supervisor_id', ''), 'supervisor_name': data.get('supervisor_name', ''), 'password': password})
        identity = get_human_identity(employee_id)
    elif identity.get('password_hash'):
        success, result = verify_identity(employee_id, password)
        if not success:
            log_audit(None, 'LOGIN_FAILED', {'id': employee_id, 'name': ''}, notes=result)
            return jsonify({"error": result}), 401
        stored_name = identity.get('full_name', '').strip()
        if provided_name and stored_name and provided_name.lower() != stored_name.lower():
            log_audit(None, 'LOGIN_FAILED', {'id': employee_id, 'name': provided_name}, notes=f"Name mismatch: provided '{provided_name}' != stored '{stored_name}'")
            return jsonify({"error": "Name stimmt nicht mit registriertem Namen überein"}), 401
    session_id = create_session(identity)
    log_audit(None, 'LOGIN_SUCCESS', {'id': identity['employee_id'], 'name': identity['full_name'], 'employee_id': identity['employee_id']}, session_id=session_id)
    return jsonify({"success": True, "session_id": session_id, "user": {"employee_id": identity['employee_id'], "full_name": identity['full_name'], "department": identity.get('department', ''), "position": identity.get('position', ''), "email": identity.get('email', ''), "supervisor_id": identity.get('supervisor_id', ''), "supervisor_name": identity.get('supervisor_name', '')}, "expires_in": CONFIG["session_timeout_minutes"] * 60})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if sess:
        log_audit(None, 'LOGOUT', {'id': sess['user_id'], 'name': sess['full_name'], 'employee_id': sess['user_id']}, session_id=session_id)
        invalidate_session(session_id)
    return jsonify({"success": True})

@app.route('/api/auth/validate', methods=['GET'])
def api_validate_session():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if not sess:
        return jsonify({"valid": False}), 401
    return jsonify({"valid": True, "user": {"employee_id": sess['user_id'], "full_name": sess['full_name']}, "remaining_seconds": CONFIG["session_timeout_minutes"] * 60})

@app.route('/api/auth/reauth', methods=['POST'])
def api_reauth():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if not sess:
        return jsonify({"error": "Session expired"}), 401
    data = request.json or {}
    success, result = verify_identity(sess['user_id'], data.get('password', ''))
    if success:
        sess['reauth_count'] += 1
        log_audit(None, 'REAUTH_SUCCESS', {'id': sess['user_id'], 'name': sess['full_name'], 'employee_id': sess['user_id']}, session_id=session_id, notes=f"Action: {data.get('action', '')}")
        return jsonify({"success": True})
    log_audit(None, 'REAUTH_FAILED', {'id': sess['user_id'], 'name': sess['full_name'], 'employee_id': sess['user_id']}, session_id=session_id)
    return jsonify({"error": result}), 401

# ============================================
# v4.7-gov NEW: Profile Update Endpoint
# ============================================
@app.route('/api/auth/profile', methods=['PUT'])
def api_update_profile():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if not sess:
        return jsonify({"error": "Session expired"}), 401
    
    data = request.json or {}
    employee_id = sess['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        UPDATE human_identities 
        SET department = ?, position = ?, email = ?, 
            supervisor_id = ?, supervisor_name = ?, updated_at = ?
        WHERE employee_id = ?
    """, (
        data.get('department', sess.get('department', '')),
        data.get('position', sess.get('position', '')),
        data.get('email', sess.get('email', '')),
        data.get('supervisor_id', ''),
        data.get('supervisor_name', ''),
        now,
        employee_id
    ))
    conn.commit()
    conn.close()
    
    sess['department'] = data.get('department', sess.get('department', ''))
    sess['position'] = data.get('position', sess.get('position', ''))
    sess['email'] = data.get('email', sess.get('email', ''))
    
    log_audit(None, 'PROFILE_UPDATED', {
        'id': employee_id, 
        'name': sess['full_name'], 
        'employee_id': employee_id
    }, session_id=session_id)
    
    return jsonify({
        "success": True, 
        "message": "Profil aktualisiert",
        "user": {
            "employee_id": employee_id,
            "full_name": sess['full_name'],
            "department": sess['department'],
            "position": sess['position'],
            "email": sess['email']
        }
    })

@app.route('/api/auth/profile', methods=['GET'])
def api_get_profile():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if not sess:
        return jsonify({"error": "Session expired"}), 401
    
    identity = get_human_identity(sess['user_id'])
    if not identity:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "employee_id": identity['employee_id'],
        "full_name": identity['full_name'],
        "department": identity.get('department', ''),
        "position": identity.get('position', ''),
        "email": identity.get('email', ''),
        "supervisor_id": identity.get('supervisor_id', ''),
        "supervisor_name": identity.get('supervisor_name', ''),
        "created_at": identity.get('created_at', '')
    })

@app.route('/api/document', methods=['POST'])
def create_document():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    data = request.json or {}
    lang = data.get('language', 'de')
    user_id = sess['user_id'] if sess else data.get('user_id', 'anonymous')
    created_by = sess['full_name'] if sess else data.get('created_by', '')
    author_data = {'id': user_id, 'name': created_by, 'employee_id': user_id, 'department': sess.get('department', '') if sess else '', 'position': sess.get('position', '') if sess else ''}
    now = datetime.now(timezone.utc).isoformat()
    doc_id = f"BABEL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO documents (id, title, content, content_html, human_fields, status, language, created_at, updated_at, user_id, created_by, dragon) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (doc_id, t("title", lang), "", "", "{}", "draft", lang, now, now, user_id, created_by, "claude"))
    conn.commit()
    conn.close()
    log_audit(doc_id, 'DOC_CREATED', author_data, session_id=session_id, new_status='draft')
    return jsonify({"id": doc_id, "title": t("title", lang), "status": "draft", "language": lang}), 201

@app.route('/api/document/<doc_id>', methods=['GET'])
def get_document(doc_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    create_migration_audit(doc_id, dict(row))
    return jsonify({"id": row["id"], "title": row["title"], "content": {"text": row["content"], "html": row["content_html"] if "content_html" in row.keys() else ""}, "human_fields": json.loads(row["human_fields"] or "{}"), "status": row["status"], "language": row["language"], "receipt": json.loads(row["receipt"]) if row["receipt"] else None, "created_at": row["created_at"], "updated_at": row["updated_at"], "created_by": row["created_by"] if "created_by" in row.keys() else "", "witness": json.loads(row["witness"]) if row["witness"] else None})

@app.route('/api/document/<doc_id>', methods=['PUT'])
def update_document(doc_id):
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    data = request.json or {}
    title = data.get('title', row["title"])
    content_data = data.get('content', {})
    if isinstance(content_data, str):
        content_data = {"text": content_data, "html": ""}
    content = content_data.get('text', row["content"])
    content_html = content_data.get('html', '')
    human_fields = json.dumps(data.get('human_fields', json.loads(row["human_fields"] or "{}")))
    modified_by = sess['full_name'] if sess else data.get('modified_by', '')
    author_data = {'id': sess['user_id'] if sess else 'unknown', 'name': modified_by, 'employee_id': sess['user_id'] if sess else '', 'position': sess.get('position', '') if sess else ''}
    witness_data = data.get('witness_data', {})
    old_status = row["status"]
    now = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    cursor.execute("UPDATE documents SET title = ?, content = ?, content_html = ?, human_fields = ?, status = 'validated', updated_at = ?, modified_by = ?, witness = ? WHERE id = ?", (title, content, content_html, human_fields, now, modified_by, json.dumps(witness_data) if witness_data else '', doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, 'DOC_UPDATED', author_data, session_id=session_id, witness_data=witness_data if witness_data.get('name') else None, old_status=old_status, new_status='validated', content_hash=content_hash)
    return jsonify({"id": doc_id, "status": "validated", "message": "Gespeichert"})

@app.route('/api/document/<doc_id>/finalize', methods=['POST'])
def finalize_document(doc_id):
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    data = request.json or {}
    witness_data = data.get('witness_data', {})
    if not witness_data.get('name'):
        return jsonify({"error": "Prüfer erforderlich", "message": t("witness_required", data.get('language', 'de'))}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    author_data = {'id': sess['user_id'] if sess else '', 'name': sess['full_name'] if sess else '', 'employee_id': sess['user_id'] if sess else '', 'department': sess.get('department', '') if sess else '', 'position': sess.get('position', '') if sess else ''}
    old_status = row["status"]
    content = {"text": row["content"], "human_fields": json.loads(row["human_fields"] or "{}"), "author": author_data, "witness": witness_data}
    receipt = make_receipt(doc_id, content, row["language"], author_data, witness_data)
    now = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(row["content"].encode()).hexdigest()[:12]
    cursor.execute("UPDATE documents SET status = 'finalized', receipt = ?, updated_at = ?, witness = ? WHERE id = ?", (json.dumps(receipt), now, json.dumps(witness_data), doc_id))
    conn.commit()
    conn.close()
    log_audit(doc_id, 'DOC_FINALIZED', author_data, session_id=session_id, witness_data=witness_data, old_status=old_status, new_status='finalized', content_hash=content_hash, notes=f'WINDI-QUITTUNG: {receipt["receipt_id"]}')
    # ─── DeepDOCFakes: Provenance Record ─────────────────────
    if DEEPDOCFAKES_AVAILABLE:
        try:
            prov_record = build_provenance_record(
                submission_id=receipt["receipt_id"],
                governance_level="HIGH",
                policy_version="2.2.0",
                isp_profile="windi_default",
                organization="WINDI Publishing House",
                content_hash=content_hash,
                metadata={"document_id": doc_id, "author": author_data.get("name", ""), "language": row["language"]}
            )
            prov_path = persist_provenance_record(prov_record)
            if prov_path:
                print(f"[WINDI-SOF] Provenance record created: {receipt['receipt_id']}")
        except Exception as e:
            print(f"[WINDI-SOF] Provenance generation error: {e}")
    return jsonify({"id": doc_id, "status": "finalized", "receipt": receipt})

@app.route('/api/document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    author_data = {'id': sess['user_id'] if sess else 'unknown', 'name': sess['full_name'] if sess else 'Anonymous', 'employee_id': sess['user_id'] if sess else ''}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    old_status = row["status"] if row else None
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    if deleted:
        log_audit(doc_id, 'DOC_DELETED', author_data, session_id=session_id, old_status=old_status)
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/documents', methods=['GET'])
def list_documents():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    user_id = sess['user_id'] if sess else request.args.get('user_id', 'anonymous')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status, language, created_at, updated_at FROM documents WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"documents": [dict(r) for r in rows]})

@app.route('/api/document/<doc_id>/audit', methods=['GET'])
def get_document_audit(doc_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM document_audit WHERE document_id = ? ORDER BY timestamp DESC", (doc_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"document_id": doc_id, "audit_trail": [dict(r) for r in rows]})

@app.route('/api/verify/<receipt_id>', methods=['GET'])
@app.route('/verify/<receipt_id>', methods=['GET'])
def verify_receipt(receipt_id):
    """
    ISP Phase 2 Enhanced Verification Endpoint.
    GET /verify/WINDI-DB-03FEB26-A1B2C3D4
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE receipt LIKE ?", (f'%{receipt_id}%',))
    row = cursor.fetchone()

    # Check submission registry as fallback
    registry_entry = None
    try:
        from engine.submission_registry import SubmissionRegistry
        registry = SubmissionRegistry("/opt/windi/provenance")
        registry_entry = registry.lookup(receipt_id)
    except:
        pass

    if not row and not registry_entry:
        conn.close()
        # Check if browser request
        accept_header = request.headers.get('Accept', '')
        wants_html = 'text/html' in accept_header and 'application/json' not in accept_header
        if wants_html:
            from datetime import datetime
            template_context = {
                "receipt_id": receipt_id,
                "status": "NOT_FOUND",
                "status_class": "invalid",
                "status_icon": "✗",
                "status_text": "NOT FOUND",
                "status_subtitle": "Receipt not in database",
                "verification_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            return render_template_string(VERIFY_HTML_TEMPLATE, **template_context), 404
        return jsonify({"status": "NOT_FOUND", "error": "Receipt not found", "receipt_id": receipt_id}), 404

    # Parse receipt and metadata
    receipt_data = {}
    doc_metadata = {}
    if row:
        try:
            if row["receipt"]:
                receipt_data = json.loads(row["receipt"])
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
        try:
            # Check if metadata column exists using row.keys()
            row_keys = row.keys()
            if "metadata" in row_keys and row["metadata"]:
                doc_metadata = json.loads(row["metadata"])
        except (KeyError, TypeError, json.JSONDecodeError):
            pass
    conn.close()

    # Extract ISP fields
    isp_profile = receipt_data.get("isp_id") or doc_metadata.get("institutional_profile")
    form_id = receipt_data.get("isp_form") or doc_metadata.get("form_id")
    governance_level = receipt_data.get("governance_level", "LOW")
    content_hash = receipt_data.get("hash", "")
    structural_hash = receipt_data.get("structural_hash") or doc_metadata.get("structural_hash", "")
    title = row["title"] if row else None
    created_at = receipt_data.get("timestamp", "")
    resilience_score = receipt_data.get("resilience_score", 0) or 0
    resilience_rating = receipt_data.get("resilience_rating", "")

    # Format hashes for display
    content_hash_display = content_hash[:12] + "..." if len(content_hash) > 12 else content_hash
    structural_hash_display = structural_hash[:12] + "..." if len(str(structural_hash)) > 12 else structural_hash

    # Get author/witness names
    author_data = receipt_data.get("author", {})
    witness_data = receipt_data.get("witness", {})
    author_name = author_data.get("name") if author_data else None
    witness_name = witness_data.get("name") if witness_data else None

    # Check if browser request (wants HTML)
    accept_header = request.headers.get('Accept', '')
    wants_html = 'text/html' in accept_header and 'application/json' not in accept_header

    if wants_html:
        # Render HTML verification page
        from datetime import datetime
        level_colors = {"LOW": "green", "MEDIUM": "blue", "HIGH": "purple"}

        # Calculate resilience class for CSS styling
        if resilience_score >= 90:
            resilience_class = "maximum"
        elif resilience_score >= 70:
            resilience_class = "high"
        elif resilience_score >= 40:
            resilience_class = "medium"
        else:
            resilience_class = "low"

        sof_protocol = receipt_data.get("sof_protocol", "v1.0")
        verification_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        template_context = {
            "receipt_id": receipt_data.get("receipt_id", receipt_id),
            "status": "VALID",
            "status_class": "valid",
            "status_icon": "✓",
            "status_text": "VERIFIED",
            "status_subtitle": "Document authenticity confirmed",
            "title": title,
            "isp_profile": isp_profile,
            "form_id": form_id,
            "created_at": created_at[:10] if created_at else None,
            "governance_level": governance_level,
            "level_color": level_colors.get(governance_level, "blue"),
            "content_hash": content_hash_display,
            "structural_hash": structural_hash_display,
            "resilience_score": resilience_score,
            "resilience_rating": resilience_rating,
            "resilience_class": resilience_class,
            "author": author_name,
            "witness": witness_name,
            "sof_protocol": sof_protocol,
            "verification_time": verification_time
        }
        return render_template_string(VERIFY_HTML_TEMPLATE, **template_context)

    # Build ISP Phase 2 JSON response
    return jsonify({
        "status": "VALID",
        "document": {
            "receipt_id": receipt_data.get("receipt_id", receipt_id),
            "document_id": row["id"] if row else None,
            "title": title,
            "created_at": created_at,
            "governance_level": governance_level,
            "isp_profile": isp_profile,
            "form_id": form_id
        },
        "integrity": {
            "content_hash": content_hash_display,
            "structural_hash": structural_hash_display,
            "status": "INTACT" if content_hash else "NO_HASH",
            "resilience_score": resilience_score,
            "resilience_rating": resilience_rating
        },
        "compliance": {
            "eu_ai_act": True,
            "sof_protocol": receipt_data.get("sof_protocol", "v1.0"),
            "human_authored": True,
            "four_eyes_principle": bool(witness_name)
        },
        "issuer": {
            "organization": "WINDI Publishing House",
            "jurisdiction": "DE",
            "principle": "AI processes. Human decides. WINDI guarantees."
        },
        "author": author_data,
        "witness": witness_data
    })

@app.route('/api/users', methods=['GET'])
def list_users():
    session_id = request.headers.get('X-Session-ID', '')
    sess = validate_session(session_id)
    if not sess:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, full_name, department, position FROM human_identities ORDER BY full_name")
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"users": [dict(r) for r in rows]})

def sanitize_content_html(html):
    """Remove governança duplicada e metaconversa LLM - v3 FINAL"""
    import re
    if not html:
        return ""
    # 1. Frases EXATAS para remover (replace simples)
    exact_remove = [
        'Human decides. I structure.',
        'KI verarbeitet. Mensch entscheidet. WINDI garantiert.',
        '**',
    ]
    for phrase in exact_remove:
        html = html.replace(phrase, '')
    # 2. Linhas INTEIRAS contendo frases de sistema (regex por linha)
    line_patterns = [
        'WINDI Publishing House',
        'EU AI Act Compliant',
        'A4 Desk BABEL',
        'WINDI-QUITTUNG',
        'Human Authorship',
        'menschlichen Autoren erstellt',
    ]
    for pattern in line_patterns:
        html = re.sub(rf'[^<]*{re.escape(pattern)}[^<]*(<br\s*/?>|$)', '', html, flags=re.IGNORECASE)
    # 3. Divs de governança estruturados
    html = re.sub(r'<div[^>]*class="[^"]*human-authorship[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div[^>]*class="[^"]*governance[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL)
    # 4. Comentários/feedback do LLM (frases descritivas no final)
    llm_feedback = [
        r'[A-Z][a-zäöü]+es [^<]*Memo[^<]*erstellt[^<]*\.?',
        r'[A-Z][a-zäöü]+er [^<]*erstellt[^<]*\.?',
        r'Soll ich [^<]*\?',
        r'Möchten Sie [^<]*\?',
        r'Entspricht das [^<]*\?',
        r'Benötigen Sie [^<]*\?',
    ]
    for pattern in llm_feedback:
        html = re.sub(pattern, '', html, flags=re.IGNORECASE)
    # 5. Limpar resíduos
    html = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>', html)
    html = re.sub(r'^(\s*<br\s*/?>\s*)+', '', html)
    html = re.sub(r'(\s*<br\s*/?>\s*)+$', '', html)
    html = re.sub(r'\*\*\s*', '', html)  # asteriscos soltos
    html = re.sub(r'v4\.[0-9]+\s*', '', html)  # versões soltas
    return html.strip()

@app.route('/api/document/<doc_id>/export/<fmt>', methods=['GET'])
def export_document(doc_id, fmt):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    if fmt not in ['docx', 'pdf', 'odt', 'rtf', 'html', 'md']:
        return jsonify({"error": "Format not supported"}), 400
    title = row["title"]
    content_html = sanitize_content_html(row["content_html"] if "content_html" in row.keys() else row["content"].replace('\n', '<br>'))
    receipt_data = json.loads(row["receipt"]) if row["receipt"] else {}
    receipt_id = receipt_data.get("receipt_id", doc_id)
    receipt_hash = receipt_data.get("hash", "---")
    author_info = receipt_data.get("author", {})
    witness_info = receipt_data.get("witness", {})
    qr_base64 = generate_qr_base64(f"WINDI:{receipt_id}|{receipt_hash}")
    # ========== PHASE 3: GOVERNANCE ==========
    from governance_phase3 import extract_block_governance, validate_structure, extract_blocks_from_html, build_governance_ledger_html, save_governance_audit
    doc_metadata = json.loads(row["metadata"]) if "metadata" in row.keys() and row["metadata"] else {}
    document_blocks = doc_metadata.get("document_structure", [])
    template_id = doc_metadata.get("template_id", "unknown")
    if not document_blocks:
        document_blocks = extract_blocks_from_html(content_html)
    governance_stats = extract_block_governance(document_blocks)
    structure_check = validate_structure(document_blocks, template_id)
    governance_ledger_html = build_governance_ledger_html(governance_stats, structure_check, template_id)
    # Phase 4: Get ISP from document metadata if available
    institutional_profile = doc_metadata.get("institutional_profile")
    
    # === ISP Integration v2.0 ===
    # Supports: templates, forms, components, tokens
    isp_css = ""
    isp_header = ""
    isp_footer = ""
    isp_full_html = None  # If set, use this instead of building HTML manually

    if institutional_profile:
        print(f"[ISP v2.0] Loading profile: {institutional_profile}")
        try:
            from isp_loader import (
                load_profile, load_tokens, load_css, load_template,
                load_component, load_form, get_logo_base64,
                render_isp_template, build_full_document
            )

            isp_data = load_profile(institutional_profile)
            tokens = load_tokens(institutional_profile)

            if isp_data:
                isp_css = load_css(institutional_profile)

                # Get template type and form ID from document metadata
                template_type = doc_metadata.get("template_type", "letter")
                form_id = doc_metadata.get("form_id")  # e.g., "transportauftrag"

                # Build context for template rendering
                template_context = {
                    "title": title,
                    "content": content_html,
                    "doc_id": doc_id,
                    "doc_date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
                    "doc_number": doc_metadata.get("doc_number", doc_id[:8]),

                    # WINDI Governance
                    "windi_receipt": receipt_id,
                    "windi_hash": receipt_hash[:16] + "..." if len(receipt_hash) > 16 else receipt_hash,
                    "windi_level": receipt_data.get("governance_level", "LOW"),
                    "windi_timestamp": datetime.now(timezone.utc).isoformat(),
                    "show_windi": True,
                    "show_windi_full": True,

                    # Author & Witness
                    "author_name": author_info.get("name", ""),
                    "author_id": author_info.get("employee_id", ""),
                    "witness_name": witness_info.get("name", ""),

                    # Resilience score
                    "resilience_score": receipt_data.get("resilience_score", "--"),
                    "resilience_rating": receipt_data.get("resilience_rating", ""),
                    "structural_hash": receipt_data.get("structural_hash", "n/a"),

                    # QR Code
                    "qr_base64": qr_base64,
                }

                # Try to build full document using ISP template system
                if form_id or template_type:
                    isp_full_html = build_full_document(
                        institutional_profile,
                        content_html,
                        template_type=template_type,
                        form_id=form_id,
                        context=template_context
                    )
                    if isp_full_html:
                        print(f"[ISP v2.0] Using ISP template: {form_id or template_type}")

                # Fallback: Load header/footer components separately
                if not isp_full_html:
                    header_component = load_component(institutional_profile, "header")
                    footer_component = load_component(institutional_profile, "footer")

                    if header_component:
                        isp_header = render_isp_template(institutional_profile, header_component, template_context)
                    else:
                        # Legacy fallback: simple logo header
                        logo_b64 = get_logo_base64(institutional_profile)
                        if logo_b64:
                            primary_color = tokens.get("colors", {}).get("primary", {}).get("red", "#000")
                            if not primary_color:
                                primary_color = isp_data.get("colors", {}).get("primary", "#000")
                            isp_header = f'''<div style="text-align:right;padding-bottom:10px;border-bottom:2px solid {primary_color};margin-bottom:15px;"><img src="data:image/svg+xml;base64,{logo_b64}" style="width:60px;"/></div>'''

                    if footer_component:
                        isp_footer = render_isp_template(institutional_profile, footer_component, template_context)

        except Exception as e:
            import traceback
            print(f"[ISP v2.0] Load error: {e}")
            traceback.print_exc()
    save_governance_audit(get_db, doc_id, governance_stats, structure_check, receipt_id, institutional_profile)
    # ========== END PHASE 3 ==========
    # v4.7-gov: Human Authorship Notice
    # v4.8: MINIMAL Human Authorship Notice (single line, discrete)
    human_authorship_notice = """
    <div style="font-size:7pt;color:#999;text-align:center;margin:10pt 0;padding:5pt 0;border-top:0.5pt solid #ddd;">
        Document governed by WINDI • Human authored • AI-assisted under supervision
    </div>
    """

    # === ISP v2.0: Use full template if available ===
    if isp_full_html:
        # Use the fully rendered ISP template
        html_content = isp_full_html
        print(f"[ISP v2.0] Using ISP full template for {doc_id}")
    else:
        # Fallback: Build HTML with components (legacy compatible)
        # Build footer: use ISP footer component if available, otherwise default
        footer_html = isp_footer if isp_footer else f'''<div class="footer" style="margin-top:15pt;padding-top:8pt;border-top:0.5pt solid #ccc;">
            <table style="width:100%;font-size:6pt;color:#888;border:none;">
                <tr style="background:none;">
                    <td style="border:none;padding:2pt;vertical-align:top;width:70%;">
                        <div>WINDI-RECEIPT: {receipt_id} | Hash: {receipt_hash}</div>
                        <div style="margin-top:2pt;">Author: {author_info.get("name","-")} ({author_info.get("employee_id","-")}) | Witness: {witness_info.get("name","-")}</div>
                        <div style="margin-top:2pt;color:#aaa;">A4 Desk BABEL v4.8 | EU AI Act Compliant | windi.publishing.de</div>
                        <div style="margin-top:3pt;">
                            <span style="background:#0d9488;color:#fff;padding:1pt 4pt;border-radius:2pt;font-size:5pt;font-weight:bold;">SOF v1.0</span>
                            <span style="background:#1a365d;color:#fff;padding:1pt 4pt;border-radius:2pt;font-size:5pt;">Resilience: {receipt_data.get("resilience_score","--")}/100 {receipt_data.get("resilience_rating","")}</span>
                            <span style="font-size:5pt;color:#aaa;">Hash: {receipt_data.get("structural_hash","n/a")}</span>
                        </div>
                    </td>
                    <td style="border:none;padding:2pt;text-align:right;vertical-align:top;width:30%;">
                        <img src="data:image/png;base64,{qr_base64}" style="width:35px;opacity:0.7;"/>
                    </td>
                </tr>
            </table>
        </div>'''

        # Build title (skip generic titles)
        title_html = f'<h1>{title}</h1>' if title not in ['Neues Dokument', 'New Document', 'Novo Documento'] else ''

        # Build authorship notice (skip if already present)
        authorship_html = human_authorship_notice if "HUMAN AUTHORSHIP" not in content_html and "menschlichen Autoren" not in content_html else ""

        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.3;
            margin: 15mm 15mm;
        }}
        table {{ page-break-inside: avoid; width: 100%; }}
        tr {{ page-break-inside: avoid; }}
        h1 {{
            font-size: 14pt;
            color: #1a365d;
            border-bottom: 2px solid #3182ce;
            padding-bottom: 6pt;
            margin-bottom: 10pt;
        }}
        .footer {{
            margin-top: 20pt;
            border-top: 2pt solid #999999;
            padding-top: 10pt;
        }}
        {isp_css}
    </style>
</head>
<body>
    {isp_header}
    {title_html}
    <div class="document-content">{content_html}</div>
    {authorship_html}
    {governance_ledger_html}
    {footer_html}
</body>
</html>'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        html_path = f.name
    try:
        if fmt == 'html':
            return send_file(html_path, as_attachment=True, download_name=f"{title}.html")
        output_path = html_path.replace('.html', f'.{fmt}')
        if fmt == 'pdf':
            WeasyHTML(filename=html_path, encoding='utf-8').write_pdf(output_path)
        else:
            subprocess.run(['pandoc', '-f', 'html', '-t', 'markdown' if fmt == 'md' else fmt, '-o', output_path, html_path], capture_output=True)
        mime_types = {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'pdf': 'application/pdf', 'odt': 'application/vnd.oasis.opendocument.text', 'rtf': 'application/rtf', 'md': 'text/markdown'}
        # === WINDI v0.1 Envelope Generation ===
        print(f"[WINDI] DEBUG: fmt={fmt}, output_path={output_path}, C14N={WINDI_C14N_AVAILABLE}", flush=True)
        if WINDI_C14N_AVAILABLE:
            try:
                with open(output_path, 'rb') as f:
                    file_bytes = f.read()
                author_data = {
                    'employee_id': author_info.get('employee_id', 'unknown'),
                    'full_name': author_info.get('name', ''),
                    'department': '',
                    'position': author_info.get('position', '')
                }
                envelope = generate_windi_envelope(doc_id, file_bytes, mime_types.get(fmt, 'application/octet-stream'), author_data, f"export.{fmt}")
                if envelope:
                    save_windi_envelope(doc_id, envelope)
                    # === WINDI Print Watermark Layer ===
                    if WINDI_PRINT_LAYER_AVAILABLE and fmt == 'pdf':
                        try:
                            doc_hash = envelope.get('integrity', {}).get('doc_hash', '')
                            if doc_hash:
                                # v4.8: Check governance level
                                from isp_loader import should_apply_watermark
                                apply_wm = should_apply_watermark(institutional_profile)
                                if apply_wm:
                                    with open(output_path, 'rb') as pf:
                                        pdf_bytes = pf.read()
                                    watermarked = embed_print_watermark(pdf_bytes, doc_hash, WINDI_ISSUER_ID)
                                    with open(output_path, 'wb') as pf:
                                        pf.write(watermarked)
                                    print(f"[WINDI] Print watermark embedded: {doc_id}", flush=True)
                                else:
                                    print(f"[WINDI] Watermark skipped (governance level): {doc_id}", flush=True)
                        except Exception as we:
                            print(f"[WINDI] Print watermark error: {we}", flush=True)
                    # === END Print Watermark ===
            except Exception as e:
                print(f"[WINDI] Export envelope error: {e}", flush=True)
        # === END WINDI ===
        return send_file(output_path, as_attachment=True, download_name=f"{title}.{fmt}", mimetype=mime_types.get(fmt, 'application/octet-stream'))
    finally:
        if os.path.exists(html_path):
            os.unlink(html_path)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message, context, dragon = data.get('message', ''), data.get('context', ''), data.get('dragon', 'claude')
    # Phase 4: ISP Resolution
    isp_profile = None
    if ISP_RESOLVER_AVAILABLE:
        isp_profile = resolve_institutional_style(message)
    if INTENT_PARSER_AVAILABLE:
        intent_result = INTENT_HANDLER.handle_message(message, request.remote_addr)
        if intent_result['handled']:
            return jsonify(intent_result)
    try:
        payload = {"message": message, "context": context, "dragon": dragon, "lang": data.get("lang", "de")}
        if isp_profile:
            payload["institutional_profile"] = isp_profile
        resp = requests.post(f"{CONFIG['gateway']}/api/chat", json=payload, timeout=60)
        return jsonify(resp.json())
    except:
        return jsonify({"error": "Gateway error"}), 503

# ═══════════════════════════════════════════════════════════════════════════════
# SANDBOX CORE - Three Dragons Deliberation
# "AI processes. Human decides. WINDI guarantees."
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/deliberate', methods=['POST'])
def deliberate():
    """
    Endpoint de deliberação multi-agente.
    Consulta ARCHITECT (GPT), GUARDIAN (Claude), WITNESS (Gemini).
    Retorna FRAME para decisão humana.
    """
    data = request.json or {}
    user_request = data.get('request', '')
    context = data.get('context', {})
    
    if not user_request:
        return jsonify({"error": "Request is required"}), 400
    
    try:
        from engine.sandbox_core import SandboxCore
        core = SandboxCore()
        frame = core.deliberate(user_request, context)
        
        return jsonify({
            "success": True,
            "session_id": frame.session_id,
            "receipt": frame.receipt,
            "timestamp": frame.timestamp,
            "architect": frame.architect,
            "guardian": frame.guardian,
            "witness": frame.witness,
            "divergence_detected": frame.divergence_detected,
            "divergence_pattern": frame.divergence_pattern,
            "consistency": frame.consistency,
            "human_action": frame.human_action,
            "options": frame.options
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "human_action": "ERROR"
        }), 500





# === i18n Translations API ===
@app.route('/api/translations')
def get_translations():
    try:
        with open(os.path.join(os.path.dirname(__file__), 'translations.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Remove _meta
        data.pop('_meta', None)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# === END i18n Translations API ===

# === Governance API Proxy (routes :8085/api/governance/* → localhost:8080/api/*) ===
@app.route('/api/governance/<path:subpath>', methods=['GET', 'POST', 'OPTIONS'])
def governance_api_proxy(subpath):
    import urllib.request
    import urllib.error
    target = f"http://localhost:8080/api/{subpath}"
    try:
        if request.method == 'POST':
            req = urllib.request.Request(
                target,
                data=request.get_data(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
        else:
            req = urllib.request.Request(target)
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read()
        from flask import Response
        return Response(body, status=resp.status, content_type='application/json',
                       headers={'Access-Control-Allow-Origin': '*'})
    except urllib.error.HTTPError as e:
        body = e.read()
        from flask import Response
        return Response(body, status=e.code, content_type='application/json')
    except Exception as e:
        return jsonify({"error": f"API proxy error: {str(e)}"}), 502
# === END Governance API Proxy ===

# === Governance Dashboard (added by dashboard deploy) ===
@app.route('/governance')
def governance_dashboard():
    return send_from_directory(STATIC_DIR, 'governance-dashboard.html')
# === END Governance Dashboard ===

# === Governance Tutorial ===
@app.route('/governance/tutorial')
def governance_tutorial():
    return send_from_directory(STATIC_DIR, 'governance-tutorial.html')
# === END Governance Tutorial ===


@app.route('/')
def index():
    return render_template_string(BABEL_HTML)

@app.route('/api/windi/verify/<doc_id>', methods=['GET', 'POST'])
def verify_windi_envelope_endpoint(doc_id):
    """Verify WINDI envelope integrity."""
    if not WINDI_C14N_AVAILABLE:
        return jsonify({"error": "WINDI C14N not available"}), 503
    envelope_path = Path(f"/opt/windi/data/envelopes/{doc_id}.envelope.json")
    if not envelope_path.exists():
        return jsonify({"error": "Envelope not found", "doc_id": doc_id}), 404
    try:
        with open(envelope_path, 'r', encoding='utf-8') as f:
            envelope = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Load failed: {e}"}), 500
    body_bytes = None
    if request.method == 'POST':
        if request.files and 'document' in request.files:
            body_bytes = request.files['document'].read()
        elif request.data:
            body_bytes = request.data
    report = verify_envelope_integrity(envelope, body_bytes)
    return jsonify({"doc_id": doc_id, "envelope": envelope, "verification": report})


@app.route('/api/windi/envelope/<doc_id>', methods=['GET'])
def get_windi_envelope_endpoint(doc_id):
    """Get WINDI envelope for a document."""
    envelope_path = Path(f"/opt/windi/data/envelopes/{doc_id}.envelope.json")
    if not envelope_path.exists():
        return jsonify({"error": "Envelope not found"}), 404
    with open(envelope_path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/windi/status', methods=['GET'])
def windi_status_endpoint():
    """WINDI v0.1 integration status."""
    envelope_dir = Path("/opt/windi/data/envelopes")
    count = len(list(envelope_dir.glob("*.envelope.json"))) if envelope_dir.exists() else 0
    return jsonify({
        "windi_c14n_available": WINDI_C14N_AVAILABLE,
        "schema_version": "0.1",
        "issuer_id": WINDI_ISSUER_ID,
        "policy_reference": WINDI_POLICY_REF,
        "envelopes_stored": count,
        "principle": "AI processes. Human decides. WINDI guarantees."
    })


# ═══════════════════════════════════════════════════════════════════════════════
# ISP TEMPLATES v2.0 - Institutional Style Profiles Integration
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/templates/available', methods=['GET'])
def api_templates_available():
    """
    List all available ISP profiles with their templates and forms.
    Used by the frontend to populate the template selector.
    """
    from isp_loader import list_profiles, load_profile, load_tokens, list_templates, list_forms

    result = []
    isp_base = Path("/opt/windi/isp")

    for folder in isp_base.iterdir():
        if folder.is_dir() and not folder.name.startswith("_") and not folder.name.startswith("."):
            profile_file = folder / "profile.json"
            if profile_file.exists():
                try:
                    profile = load_profile(folder.name)
                    tokens = load_tokens(folder.name)
                    templates = list_templates(folder.name)
                    forms = list_forms(folder.name)

                    # Get primary color from tokens or profile
                    primary_color = "#1a365d"  # default
                    if tokens and "colors" in tokens:
                        primary_color = tokens.get("colors", {}).get("primary", {}).get("red", primary_color)
                    elif profile and "colors" in profile:
                        primary_color = profile.get("colors", {}).get("primary", primary_color)

                    result.append({
                        "id": folder.name,
                        "name": profile.get("organization", {}).get("organization_name", folder.name),
                        "short_name": folder.name.replace("-", " ").title(),
                        "jurisdiction": profile.get("organization", {}).get("jurisdiction", ""),
                        "sector": profile.get("organization", {}).get("sector", ""),
                        "governance_level": profile.get("governance", {}).get("default_level", "LOW"),
                        "primary_color": primary_color,
                        "templates": templates,
                        "forms": forms,
                        "has_tokens": bool(tokens),
                    })
                except Exception as e:
                    print(f"[ISP] Error loading {folder.name}: {e}")

    return jsonify({
        "profiles": result,
        "count": len(result)
    })


@app.route('/api/templates/isp/<profile_id>/form/<form_name>', methods=['GET'])
def api_get_isp_form_html(profile_id, form_name):
    """
    Get rendered HTML for an ISP form, ready to display in editor.
    """
    from isp_loader import load_form, load_css, render_isp_template, load_profile

    form_html = load_form(profile_id, form_name)
    if not form_html:
        return jsonify({"error": "Form not found", "profile_id": profile_id, "form_name": form_name}), 404

    # Get CSS and embed it
    css = load_css(profile_id)
    profile = load_profile(profile_id)

    # Build context for rendering
    from datetime import datetime
    context = {
        "doc_date": datetime.now().strftime("%d.%m.%Y"),
        "windi_level": profile.get("governance", {}).get("default_level", "LOW") if profile else "LOW",
        "windi_receipt": "PREVIEW",
        "show_windi": True,
    }

    # Render template with Jinja2
    rendered_html = render_isp_template(profile_id, form_html, context)

    # Replace external CSS link with inline CSS
    if css:
        rendered_html = rendered_html.replace(
            '<link rel="stylesheet" href="../styles.css">',
            f'<style>{css}</style>'
        )

    return jsonify({
        "html": rendered_html,
        "profile_id": profile_id,
        "form_name": form_name,
        "form_id": f"{profile_id}:{form_name}",
        "governance_level": context["windi_level"]
    })


@app.route('/api/templates/isp/<profile_id>/template/<template_name>', methods=['GET'])
def api_get_isp_template_html(profile_id, template_name):
    """
    Get rendered HTML for an ISP template, ready to display in editor.
    """
    from isp_loader import load_template, load_css, render_isp_template, load_profile

    template_html = load_template(profile_id, template_name)
    if not template_html:
        return jsonify({"error": "Template not found", "profile_id": profile_id, "template_name": template_name}), 404

    css = load_css(profile_id)
    profile = load_profile(profile_id)

    from datetime import datetime
    context = {
        "doc_date": datetime.now().strftime("%d.%m.%Y"),
        "title": "",
        "content": "",
        "windi_level": profile.get("governance", {}).get("default_level", "LOW") if profile else "LOW",
        "windi_receipt": "PREVIEW",
        "show_windi": True,
    }

    rendered_html = render_isp_template(profile_id, template_html, context)

    if css:
        rendered_html = rendered_html.replace(
            '<link rel="stylesheet" href="../styles.css">',
            f'<style>{css}</style>'
        )

    return jsonify({
        "html": rendered_html,
        "profile_id": profile_id,
        "template_name": template_name,
        "template_id": f"{profile_id}:{template_name}",
        "governance_level": context["windi_level"]
    })

# ═══════════════════════════════════════════════════════════════════════════════
# END ISP TEMPLATES v2.0
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3A: HTML VERIFICATION PAGE TEMPLATE
# "AI processes. Human decides. WINDI guarantees."
# ═══════════════════════════════════════════════════════════════════════════════

VERIFY_HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WINDI Verification - {{ receipt_id }}</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🐉</text></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh; padding: 20px;
            color: #fff;
        }
        .container { max-width: 500px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 20px; }
        .header-logo { font-size: 48px; margin-bottom: 8px; }
        .header-title { font-size: 14px; letter-spacing: 2px; color: #94a3b8; text-transform: uppercase; }
        .card { background: rgba(255,255,255,0.1); border-radius: 16px; padding: 24px; margin-bottom: 16px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .status-valid { background: linear-gradient(135deg, #10b981 0%, #059669 100%); text-align: center; border: none; }
        .status-invalid { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); text-align: center; border: none; }
        .status-partial { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); text-align: center; border: none; }
        .status-icon { font-size: 64px; margin-bottom: 12px; }
        .status-text { font-size: 28px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; }
        .status-subtitle { font-size: 14px; opacity: 0.9; margin-top: 8px; }
        .receipt-id { font-family: 'Courier New', monospace; font-size: 11px; opacity: 0.8; margin-top: 12px; word-break: break-all; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 8px; }
        .section-title { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; text-transform: uppercase; letter-spacing: 1px; }
        .detail-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { color: #94a3b8; font-size: 13px; }
        .detail-value { font-weight: 500; text-align: right; font-family: 'Courier New', monospace; font-size: 13px; max-width: 60%; word-break: break-all; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .badge-green { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
        .badge-blue { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
        .badge-purple { background: rgba(139, 92, 246, 0.2); color: #a78bfa; border: 1px solid #8b5cf6; }
        .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
        .badge-red { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
        .resilience-container { margin-top: 8px; }
        .resilience-bar { height: 8px; background: rgba(255,255,255,0.2); border-radius: 4px; overflow: hidden; }
        .resilience-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
        .resilience-fill.maximum { background: linear-gradient(90deg, #10b981, #3b82f6); }
        .resilience-fill.high { background: linear-gradient(90deg, #3b82f6, #8b5cf6); }
        .resilience-fill.medium { background: linear-gradient(90deg, #f59e0b, #ef4444); }
        .resilience-fill.low { background: #ef4444; }
        .footer { text-align: center; padding: 24px 20px; color: #64748b; font-size: 12px; }
        .footer-motto { font-style: italic; margin-bottom: 12px; color: #94a3b8; }
        .footer-org { margin-bottom: 4px; }
        .footer-link { color: #3b82f6; text-decoration: none; }
        .timestamp { font-size: 11px; color: #64748b; text-align: center; margin-top: 8px; }
        .isp-badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.1); padding: 6px 12px; border-radius: 8px; margin-top: 8px; }
        .isp-badge img { height: 16px; }
        .error-details { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); border-radius: 8px; padding: 16px; margin-top: 16px; }
        .error-details code { font-family: monospace; font-size: 12px; color: #f87171; }
        @media (max-width: 380px) {
            .detail-row { flex-direction: column; align-items: flex-start; gap: 4px; }
            .detail-value { text-align: left; max-width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-logo">🐉</div>
            <div class="header-title">WINDI Verification</div>
        </div>

        <div class="card status-{{ status_class }}">
            <div class="status-icon">{{ status_icon }}</div>
            <div class="status-text">{{ status_text }}</div>
            <div class="status-subtitle">{{ status_subtitle }}</div>
            <div class="receipt-id">{{ receipt_id }}</div>
        </div>

        {% if status == 'VALID' or status == 'PARTIAL' %}
        <div class="card">
            <div class="section-title">📄 Document</div>
            {% if title %}
            <div class="detail-row">
                <span class="detail-label">Title</span>
                <span class="detail-value">{{ title }}</span>
            </div>
            {% endif %}
            {% if isp_profile %}
            <div class="detail-row">
                <span class="detail-label">Institution</span>
                <span class="detail-value">{{ isp_profile }}</span>
            </div>
            {% endif %}
            {% if form_id %}
            <div class="detail-row">
                <span class="detail-label">Form</span>
                <span class="detail-value">{{ form_id }}</span>
            </div>
            {% endif %}
            {% if created_at %}
            <div class="detail-row">
                <span class="detail-label">Created</span>
                <span class="detail-value">{{ created_at }}</span>
            </div>
            {% endif %}
            <div class="detail-row">
                <span class="detail-label">Governance</span>
                <span class="badge badge-{{ level_color }}">{{ governance_level }}</span>
            </div>
        </div>

        <div class="card">
            <div class="section-title">🔐 Integrity</div>
            <div class="detail-row">
                <span class="detail-label">Content Hash</span>
                <span class="detail-value">{{ content_hash or 'N/A' }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Structural Hash</span>
                <span class="detail-value">{{ structural_hash or 'N/A' }}</span>
            </div>
            {% if resilience_score %}
            <div class="detail-row">
                <span class="detail-label">Resilience</span>
                <span class="detail-value">{{ resilience_score }}/100</span>
            </div>
            <div class="resilience-container">
                <div class="resilience-bar">
                    <div class="resilience-fill {{ resilience_class }}" style="width: {{ resilience_score }}%"></div>
                </div>
            </div>
            {% if resilience_rating %}
            <div class="timestamp">{{ resilience_rating }}</div>
            {% endif %}
            {% endif %}
        </div>

        {% if author or witness %}
        <div class="card">
            <div class="section-title">👥 Human Roles</div>
            {% if author %}
            <div class="detail-row">
                <span class="detail-label">Author</span>
                <span class="detail-value">{{ author }}</span>
            </div>
            {% endif %}
            {% if witness %}
            <div class="detail-row">
                <span class="detail-label">Witness</span>
                <span class="detail-value">{{ witness }}</span>
            </div>
            {% endif %}
            <div class="detail-row">
                <span class="detail-label">Four-Eyes</span>
                <span class="badge badge-{{ 'green' if witness else 'yellow' }}">{{ 'Active' if witness else 'Single' }}</span>
            </div>
        </div>
        {% endif %}

        <div class="card">
            <div class="section-title">🏛️ Compliance</div>
            <div class="detail-row">
                <span class="detail-label">EU AI Act</span>
                <span class="badge badge-green">✓ Compliant</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">SOF Protocol</span>
                <span class="badge badge-blue">{{ sof_protocol or 'v1.0' }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Human Decision</span>
                <span class="badge badge-purple">✓ Guaranteed</span>
            </div>
        </div>
        {% endif %}

        {% if status == 'NOT_FOUND' %}
        <div class="card">
            <div class="section-title">ℹ️ Information</div>
            <p style="color: #94a3b8; line-height: 1.6;">
                This receipt ID was not found in our verification database.
                This could mean:
            </p>
            <ul style="color: #94a3b8; margin: 16px 0; padding-left: 20px; line-height: 1.8;">
                <li>The document hasn't been finalized yet</li>
                <li>The receipt ID was entered incorrectly</li>
                <li>The document was created in a different system</li>
            </ul>
            <p style="color: #64748b; font-size: 12px;">
                If you believe this is an error, please contact WINDI support.
            </p>
        </div>
        {% endif %}

        {% if error_message %}
        <div class="error-details">
            <div class="section-title" style="color: #f87171;">⚠️ Error Details</div>
            <code>{{ error_message }}</code>
        </div>
        {% endif %}

        <div class="footer">
            <div class="footer-motto">"AI processes. Human decides. WINDI guarantees."</div>
            <div class="footer-org">WINDI Publishing House · Kempten, Bavaria</div>
            <a href="https://windia4desk.tech" class="footer-link">windia4desk.tech</a>
        </div>

        <div class="timestamp">
            Verified at {{ verification_time }}
        </div>
    </div>
</body>
</html>
'''

# Using raw string (r-prefix) for JavaScript regex patterns
BABEL_HTML = r'''<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>A4 Desk BABEL v4.7-gov</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><link rel="stylesheet" href="/static/windi_v47.css"><link rel="stylesheet" href="/static/windi_v47.css"><style>*{margin:0;padding:0;box-sizing:border-box}:root{--primary:#1a365d;--accent:#3182ce;--success:#38a169;--warning:#d69e2e;--danger:#e53e3e;--bg:#f7fafc;--card:#fff;--text:#2d3748;--border:#e2e8f0}body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}.login-overlay{position:fixed;inset:0;background:linear-gradient(135deg,#1a365d,#2c5282);display:flex;align-items:center;justify-content:center;z-index:10000}.login-modal{background:#fff;border-radius:16px;padding:40px;max-width:500px;width:95%;max-height:90vh;overflow-y:auto}.login-header{text-align:center;margin-bottom:25px}.login-header .icon{font-size:56px}.login-header h1{color:var(--primary);font-size:1.6rem}.form-section{background:#f8fafc;border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px}.form-section-title{display:flex;align-items:center;gap:8px;font-weight:600;color:var(--primary);margin-bottom:12px}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}.form-row.single{grid-template-columns:1fr}.form-field{display:flex;flex-direction:column;gap:4px}.form-field label{font-size:.8rem;font-weight:600}.form-field .required{color:#dc2626}.form-field input,.form-field select{padding:10px;border:2px solid var(--border);border-radius:6px}.form-field input:focus{outline:none;border-color:var(--accent)}.form-field small{font-size:.7rem;color:#718096}.login-btn{width:100%;padding:14px;background:linear-gradient(135deg,#999999,#AAAAAA);color:#fff;border:none;border-radius:10px;cursor:pointer;font-weight:700;font-size:1rem;margin-top:10px}.login-principle{background:#F5F5F5;border:1px dashed #AAAAAA;padding:12px;border-radius:8px;text-align:center;margin-top:15px;font-size:.85rem;color:#777777;font-weight:600}.migration-notice{background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:15px;font-size:.85rem;color:#92400e}.session-bar{position:fixed;top:0;left:0;right:0;height:40px;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:9000;font-size:.85rem}.session-bar .user-info{display:flex;align-items:center;gap:15px}.session-bar .btn-profile{background:transparent;border:1px solid rgba(255,255,255,0.3);color:#fff;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:.8rem}.session-bar .btn-profile:hover{background:rgba(255,255,255,0.1)}.session-bar .timer.warning{color:#fbbf24;animation:pulse 1s infinite}.session-bar .btn-logout{background:var(--danger);border:none;color:#fff;padding:5px 15px;border-radius:4px;cursor:pointer}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}.app-content{margin-top:40px;display:flex;min-height:calc(100vh - 40px)}.sidebar{width:280px;background:var(--primary);color:#fff;padding:20px;flex-shrink:0}.sidebar.collapsed{width:0;padding:0;overflow:hidden}.sidebar-toggle{position:fixed;left:10px;top:50px;z-index:1000;background:var(--primary);color:#fff;border:none;width:40px;height:40px;border-radius:8px;cursor:pointer}.logo{display:flex;align-items:center;gap:10px;margin:30px 0 20px}.logo i{font-size:2rem;color:var(--accent)}.lang-bar{display:flex;gap:5px;margin-bottom:20px}.lang-btn{background:#2c5282;border:none;color:#fff;padding:5px 10px;border-radius:4px;cursor:pointer}.lang-btn.active{background:var(--accent)}.btn-new{width:100%;padding:12px;background:var(--success);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;margin-bottom:20px}.doc-list{max-height:calc(100vh - 350px);overflow-y:auto}.doc-item{padding:12px;background:#2c5282;border-radius:6px;margin-bottom:8px;cursor:pointer;font-size:.85rem;display:flex;justify-content:space-between}.doc-item:hover{background:var(--accent)}.doc-item-delete{background:var(--danger);color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer}.main-area{flex:1;display:flex;flex-direction:column}.top-bar{background:var(--card);padding:10px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:15px;flex-wrap:wrap}.top-bar-title{font-size:1.1rem;font-weight:600;color:var(--primary);margin-left:50px}.top-bar-actions{display:flex;gap:8px;margin-left:auto}.top-bar-btn{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:.85rem}.btn-save{background:var(--primary);color:#fff}.btn-finalize{background:var(--success);color:#fff}.btn-delete{background:var(--danger);color:#fff}.btn-settings{background:var(--accent);color:#fff}.status-badge{padding:6px 12px;border-radius:20px;font-size:.8rem;font-weight:600}.status-draft{background:#fef3c7;color:#92400e}.status-validated{background:#d1fae5;color:#777777}.status-finalized{background:#dbeafe;color:#1e40af}.content-area{flex:1;display:flex;overflow:hidden}.editor-section{flex:1;display:flex;flex-direction:column;padding:20px;overflow-y:auto}.title-input{width:100%;font-size:1.5rem;font-weight:700;border:none;border-bottom:2px solid var(--border);padding:10px 0;margin-bottom:15px;color:var(--primary);background:transparent}.title-input:focus{outline:none;border-color:var(--accent)}.editor-toolbar{display:flex;gap:5px;padding:10px;background:var(--bg);border-radius:8px;margin-bottom:10px}.toolbar-btn{background:#fff;border:1px solid var(--border);padding:8px 12px;border-radius:4px;cursor:pointer}.toolbar-btn:hover{background:var(--accent);color:#fff}#editor{flex:1;border:1px solid var(--border);border-radius:8px;padding:20px;font-size:1rem;line-height:1.8;background:#fff;overflow-y:auto;min-height:200px}#editor:focus{outline:none;border-color:var(--accent)}.chat-section{width:40%;min-width:320px;display:flex;flex-direction:column;border-left:1px solid var(--border)}.chat-header{padding:15px;background:var(--primary);color:#fff}.chat-messages{flex:1;overflow-y:auto;padding:20px;background:var(--bg)}.chat-msg{padding:12px;border-radius:12px;margin-bottom:12px;max-width:90%;white-space:pre-wrap}.chat-user{background:var(--primary);color:#fff;margin-left:auto}.chat-ai{background:#fff;border:1px solid var(--border)}.insert-btn{margin-top:10px;padding:8px 16px;background:var(--success);color:#fff;border:none;border-radius:6px;cursor:pointer}.preview-btn{margin-top:10px;margin-right:8px;padding:8px 16px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer}.chat-input-area{padding:15px;background:#fff;border-top:1px solid var(--border)}.chat-textarea{width:100%;min-height:80px;padding:12px;border:1px solid var(--border);border-radius:8px;resize:vertical;margin-bottom:10px}.chat-actions{display:flex;gap:10px;justify-content:flex-end}.chat-send{padding:10px 20px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600}.chat-send-doc{padding:10px 20px;background:var(--warning);color:#fff;border:none;border-radius:8px;cursor:pointer}.settings-panel{width:340px;background:var(--card);border-left:1px solid var(--border);padding:20px;overflow-y:auto}.settings-panel.collapsed{width:0;padding:0;overflow:hidden}.panel-toggle{position:fixed;right:10px;top:50px;z-index:1000;background:var(--accent);color:#fff;border:none;width:40px;height:40px;border-radius:8px;cursor:pointer}.panel-section{margin-bottom:25px}.panel-title{font-size:.9rem;font-weight:600;color:var(--primary);margin-bottom:10px}.human-field{margin-bottom:15px}.human-field label{display:block;font-size:.85rem;color:#718096;margin-bottom:5px}.human-field input,.human-field select{width:100%;padding:10px;border:1px solid var(--border);border-radius:6px}.human-field input:read-only{background:#f1f5f9}.human-field small{color:var(--warning);font-size:.75rem}.witness-section{background:#fefce8;border:1px dashed #eab308;border-radius:8px;padding:15px;margin-top:15px}.export-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.btn-export{background:#805ad5;color:#fff;padding:8px;border:none;border-radius:6px;cursor:pointer}.receipt-box{background:var(--bg);border:1px solid var(--success);border-radius:8px;padding:15px;font-family:monospace;font-size:.75rem;display:none;margin-top:15px}.receipt-box.show{display:block}.panel-section:first-child{position:sticky;top:0;background:var(--card);z-index:10;padding-bottom:10px;border-bottom:1px solid var(--border)}.witness-section{position:sticky;top:160px;background:#fefce8;z-index:9}.chat-content{white-space:pre-wrap}.chat-content.collapsed{max-height:150px;overflow:hidden;position:relative}.chat-content.collapsed::after{content:'';position:absolute;bottom:0;left:0;right:0;height:40px;background:linear-gradient(transparent,#fff)}.expand-btn{background:transparent;border:1px dashed var(--accent);color:var(--accent);padding:4px 12px;border-radius:4px;cursor:pointer;margin:8px 0;display:block;width:100%;text-align:center}.reauth-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:10001}.reauth-overlay.show{display:flex}.reauth-modal{background:#fff;border-radius:16px;padding:30px;max-width:400px;width:95%}.reauth-modal h3{color:var(--primary);margin-bottom:10px}.reauth-modal input{width:100%;padding:12px;border:2px solid var(--border);border-radius:8px;margin-bottom:15px}.reauth-buttons{display:flex;gap:10px}.reauth-buttons button{flex:1;padding:12px;border:none;border-radius:8px;cursor:pointer;font-weight:600}.btn-reauth-confirm{background:var(--success);color:#fff}.btn-reauth-cancel{background:#718096;color:#fff}.profile-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:10001}.profile-overlay.show{display:flex}.profile-modal{background:#fff;border-radius:16px;padding:30px;max-width:500px;width:95%;max-height:90vh;overflow-y:auto}.profile-modal h3{color:var(--primary);margin-bottom:20px;display:flex;align-items:center;gap:10px}.profile-form .form-field{margin-bottom:15px}.profile-form label{display:block;font-size:.85rem;font-weight:600;color:#4a5568;margin-bottom:5px}.profile-form input{width:100%;padding:12px;border:2px solid var(--border);border-radius:8px}.profile-form input:read-only{background:#f1f5f9;color:#718096}.profile-form input:focus{outline:none;border-color:var(--accent)}.profile-buttons{display:flex;gap:10px;margin-top:20px}.profile-buttons button{flex:1;padding:12px;border:none;border-radius:8px;cursor:pointer;font-weight:600}.btn-profile-save{background:var(--success);color:#fff}.btn-profile-cancel{background:#718096;color:#fff}.preview-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:10001}.preview-overlay.show{display:flex}.preview-modal{background:#fff;border-radius:16px;padding:30px;max-width:800px;width:95%;max-height:90vh;overflow-y:auto}.preview-modal h3{color:var(--primary);margin-bottom:20px;display:flex;align-items:center;gap:10px}.preview-content{background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:20px;min-height:200px;max-height:400px;overflow-y:auto;white-space:pre-wrap;line-height:1.8}.preview-buttons{display:flex;gap:10px;margin-top:20px}.preview-buttons button{flex:1;padding:12px;border:none;border-radius:8px;cursor:pointer;font-weight:600}.btn-preview-insert{background:var(--success);color:#fff}.btn-preview-cancel{background:#718096;color:#fff}.toast{position:fixed;bottom:20px;right:20px;padding:15px 25px;border-radius:8px;color:#fff;font-weight:600;z-index:10002}.toast-success{background:var(--success)}.toast-error{background:var(--danger)}.toast-warning{background:var(--warning)}.template-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:10001}.template-overlay.show{display:flex}.template-modal{background:#fff;border-radius:16px;padding:30px;max-width:700px;width:95%;max-height:90vh;overflow-y:auto}.template-modal h3{color:var(--primary);margin-bottom:20px}.template-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px}.template-card{border:2px solid var(--border);border-radius:12px;padding:15px;cursor:pointer;transition:all .2s}.template-card:hover{border-color:var(--accent);transform:translateY(-2px)}.template-card.selected{border-color:var(--success);background:#F5F5F5}.template-card-header{height:40px;border-radius:6px;margin-bottom:10px}.template-card-name{font-weight:600;font-size:.9rem;margin-bottom:5px}.template-card-desc{font-size:.75rem;color:#718096}.template-card-langs{display:flex;gap:4px;margin-top:8px;flex-wrap:wrap}.template-card-lang{font-size:.65rem;background:#e2e8f0;padding:2px 6px;border-radius:4px}.template-buttons{display:flex;gap:10px;margin-top:20px}.template-buttons button{flex:1;padding:12px;border:none;border-radius:8px;cursor:pointer;font-weight:600}.btn-template-apply{background:var(--success);color:#fff}.btn-template-cancel{background:#718096;color:#fff}@media(max-width:900px){.content-area{flex-direction:column}.chat-section{width:100%;border-left:none;border-top:1px solid var(--border)}.form-row{grid-template-columns:1fr}}</style></head><body>

<div class="login-overlay" id="loginOverlay"><div class="login-modal"><div class="login-header"><div class="icon">🏛️</div><h1>WINDI Publishing House</h1><p>Human Identity Card</p></div><div class="migration-notice" id="migrationNotice" style="display:none"><strong>ℹ️ System aktualisiert.</strong> Zur Nutzung ergänzen Sie Ihre Mitarbeiter-ID und Passwort.</div><form onsubmit="handleLogin(event)"><div class="form-section"><div class="form-section-title"><i class="fas fa-user"></i> Persönliche Daten</div><div class="form-row"><div class="form-field"><label>Name <span class="required">*</span></label><input type="text" id="loginFullName" required placeholder="Max Mustermann"></div><div class="form-field"><label>Mitarbeiter-ID <span class="required">*</span></label><input type="text" id="loginEmployeeId" required placeholder="EMP-2024-0042"></div></div><div class="form-row"><div class="form-field"><label>Abteilung</label><input type="text" id="loginDepartment" placeholder="Bauamt"></div><div class="form-field"><label>Position</label><input type="text" id="loginPosition" placeholder="Sachbearbeiter"></div></div><div class="form-row single"><div class="form-field"><label>E-Mail</label><input type="email" id="loginEmail" placeholder="max@behoerde.de"></div></div><div class="form-row single"><div class="form-field"><label>Passwort <span class="required">*</span></label><input type="password" id="loginPassword" required placeholder="Ihr Passwort"><small>Bei Erstanmeldung wird dieses Passwort gespeichert.</small></div></div></div><div class="form-section"><div class="form-section-title"><i class="fas fa-sitemap"></i> Hierarchie (optional)</div><div class="form-row"><div class="form-field"><label>Vorgesetzter-ID</label><input type="text" id="loginSupervisorId" placeholder="EMP-2024-0001"></div><div class="form-field"><label>Vorgesetzter Name</label><input type="text" id="loginSupervisorName" placeholder="Dr. Schmidt"></div></div></div><button type="submit" class="login-btn"><i class="fas fa-sign-in-alt"></i> Anmelden</button><div class="login-principle">🔒 KI verarbeitet. Mensch entscheidet. WINDI garantiert.</div></form></div></div>

<div class="reauth-overlay" id="reauthOverlay"><div class="reauth-modal"><h3><i class="fas fa-shield-alt"></i> Re-Authentifizierung</h3><p>Passwort bestätigen:</p><input type="password" id="reauthPassword" placeholder="Passwort"><div class="reauth-buttons"><button class="btn-reauth-cancel" onclick="hideReauth()">Abbrechen</button><button class="btn-reauth-confirm" onclick="confirmReauth()">Bestätigen</button></div></div></div>

<!-- v4.7-gov: Profile Modal -->
<div class="profile-overlay" id="profileOverlay"><div class="profile-modal"><h3><i class="fas fa-user-edit"></i> Mein Profil</h3><div class="profile-form"><div class="form-field"><label>Name</label><input type="text" id="profileFullName" readonly></div><div class="form-field"><label>Mitarbeiter-ID</label><input type="text" id="profileEmployeeId" readonly></div><div class="form-field"><label>Abteilung</label><input type="text" id="profileDepartment" placeholder="Abteilung eingeben..."></div><div class="form-field"><label>Position</label><input type="text" id="profilePosition" placeholder="Position eingeben..."></div><div class="form-field"><label>E-Mail</label><input type="email" id="profileEmail" placeholder="email@beispiel.de"></div><div class="form-field"><label>Vorgesetzter-ID</label><input type="text" id="profileSupervisorId" placeholder="EMP-..."></div><div class="form-field"><label>Vorgesetzter Name</label><input type="text" id="profileSupervisorName" placeholder="Name des Vorgesetzten"></div></div><div class="profile-buttons"><button class="btn-profile-cancel" onclick="hideProfile()">Abbrechen</button><button class="btn-profile-save" onclick="saveProfile()"><i class="fas fa-save"></i> Speichern</button></div></div></div>

<!-- v4.7-gov: Preview Modal -->
<div class="preview-overlay" id="previewOverlay"><div class="preview-modal"><h3><i class="fas fa-eye"></i> Vorschau</h3><div class="preview-content" id="previewContent"></div><div class="preview-buttons"><button class="btn-preview-cancel" onclick="hidePreview()">Abbrechen</button><button class="btn-preview-insert" onclick="confirmInsert()"><i class="fas fa-plus"></i> Einfügen</button></div></div></div>

<div class="template-overlay" id="templateOverlay"><div class="template-modal"><h3><i class="fas fa-file-alt"></i> Template auswählen</h3><div class="template-grid" id="templateGrid"><div style="text-align:center;padding:20px"><i class="fas fa-spinner fa-spin"></i> Laden...</div></div><div class="template-buttons"><button class="btn-template-cancel" onclick="hideTemplateModal()">Abbrechen</button><button class="btn-template-apply" onclick="applySelectedTemplate()"><i class="fas fa-check"></i> Anwenden</button></div></div></div><div class="session-bar" id="sessionBar" style="display:none"><div class="user-info"><span><i class="fas fa-user-circle"></i> <span id="sessionUserName">-</span> | <span id="sessionUserId">-</span></span><button class="btn-profile" onclick="showProfile()"><i class="fas fa-user-edit"></i> Mein Profil</button><button class="btn-profile" onclick="window.location.href='/governance'" style="background:rgba(210,153,34,.2);border-color:rgba(210,153,34,.4);"><i class="fas fa-shield-alt"></i> Governance</button></div><div class="timer" id="sessionTimer"><i class="fas fa-clock"></i> <span id="sessionTimeLeft">10:00</span></div><button class="btn-logout" onclick="handleLogout()"><i class="fas fa-sign-out-alt"></i> Abmelden</button></div>

<div class="app-content" id="appContent" style="display:none"><button class="sidebar-toggle" onclick="toggleSidebar()"><i class="fas fa-bars"></i></button><aside class="sidebar" id="sidebar"><div class="logo"><i class="fas fa-landmark"></i><div><h1>A4 Desk BABEL</h1><small>v4.7-gov</small></div></div><div class="lang-bar" id="langBar"></div><button class="btn-new" onclick="newDoc()"><i class="fas fa-plus"></i> Neues Dokument</button><div class="doc-list" id="docList"></div></aside><div class="main-area"><div class="top-bar"><span class="top-bar-title">A4 Desk BABEL v4.7-gov</span><div id="statusBadge" class="status-badge status-draft">Entwurf</div><div class="top-bar-actions"><button class="top-bar-btn btn-save" onclick="saveDoc()"><i class="fas fa-save"></i> Speichern</button><button class="top-bar-btn btn-finalize" onclick="finalizeDoc()"><i class="fas fa-check"></i> Abschließen</button><button class="top-bar-btn btn-delete" onclick="deleteCurrentDoc()"><i class="fas fa-trash"></i></button><button class="top-bar-btn btn-settings" onclick="togglePanel()"><i class="fas fa-cog"></i></button></div></div><div class="content-area"><div class="editor-section"><input type="text" class="title-input" id="docTitle" placeholder="Neues Dokument"><div class="editor-toolbar"><button class="toolbar-btn" onclick="execCmd('bold')"><i class="fas fa-bold"></i></button><button class="toolbar-btn" onclick="execCmd('italic')"><i class="fas fa-italic"></i></button><button class="toolbar-btn" onclick="execCmd('underline')"><i class="fas fa-underline"></i></button><button class="toolbar-btn" onclick="showTemplateModal()" title="ISP Templates" style="background:#EC0016;color:#fff;font-weight:600;"><i class="fas fa-building"></i> ISP</button><button class="toolbar-btn" onclick="execCmd('insertUnorderedList')"><i class="fas fa-list-ul"></i></button><button class="toolbar-btn" onclick="execCmd('insertOrderedList')"><i class="fas fa-list-ol"></i></button></div><div id="editor" contenteditable="true"></div></div><div class="chat-section"><div class="chat-header"><i class="fas fa-dragon"></i> WINDI LLM Chat</div><div class="chat-messages" id="chatMessages"><div class="chat-msg chat-ai">Willkommen! Wie kann ich helfen?</div></div><div class="chat-input-area"><textarea class="chat-textarea" id="chatInput" placeholder="Nachricht..."></textarea><div class="chat-actions"><button class="chat-send-doc" onclick="sendDocToChat()"><i class="fas fa-file-export"></i> Doc→Chat</button><button class="chat-send" onclick="sendChat()"><i class="fas fa-paper-plane"></i> Senden</button></div></div></div></div></div><aside class="settings-panel collapsed" id="settingsPanel"><div class="panel-section"><div class="panel-title"><i class="fas fa-user"></i> Autor</div><div class="human-field"><label>Name</label><input type="text" id="fieldAuthorName" readonly></div><div class="human-field"><label>ID</label><input type="text" id="fieldAuthorId" readonly></div><div class="human-field"><label>Datum</label><input type="date" id="fieldDate"><small>🔒 Nur Mensch</small></div></div><div class="witness-section"><div class="panel-title" style="color:#854d0e"><i class="fas fa-eye"></i> Prüfer</div><div class="human-field"><label>Name *</label><input type="text" id="fieldWitnessName" placeholder="Name eingeben..." list="witnessList" onchange="fillWitnessData(this.value)"><datalist id="witnessList"></datalist><small>🔒 Erforderlich</small></div><div class="human-field"><label>ID</label><input type="text" id="fieldWitnessId" placeholder="ID eingeben..."></div><div class="human-field"><label>Position</label><input type="text" id="fieldWitnessPosition" placeholder="Position eingeben..."></div><div class="human-field"><label>Beziehung</label><select id="fieldWitnessRelation"><option value="">-- Auswählen --</option><option value="supervisor">Vorgesetzter</option><option value="compliance">Compliance</option><option value="peer">Peer</option><option value="external">Extern</option></select></div></div><div class="panel-section"><div class="panel-title"><i class="fas fa-file-export"></i> Export</div><div class="export-grid"><button class="btn-export" onclick="exportDoc('odt')">ODT</button><button class="btn-export" onclick="exportDoc('docx')">DOCX</button><button class="btn-export" onclick="exportDoc('pdf')">PDF</button><button class="btn-export" onclick="exportDoc('html')">HTML</button><button class="btn-export" onclick="exportDoc('rtf')">RTF</button><button class="btn-export" onclick="exportDoc('md')">MD</button></div></div><div class="receipt-box" id="receiptBox"></div></aside><button class="panel-toggle" onclick="togglePanel()"><i class="fas fa-cog"></i></button></div>

<script>
const CONFIG={sessionTimeoutMinutes:30,warningTimeSeconds:60};
const LANGS={de:{flag:'🇩🇪'},en:{flag:'🇬🇧'},pt:{flag:'🇧🇷'}};
const T={de:{draft:'Entwurf',validated:'Validiert',finalized:'Abgeschlossen',witness_required:'Prüfer erforderlich'},en:{draft:'Draft',validated:'Validated',finalized:'Finalized',witness_required:'Witness required'},pt:{draft:'Rascunho',validated:'Validado',finalized:'Finalizado',witness_required:'Testemunha necessária'}};
let currentLang='de',docId=null,sessionId=null,sessionTimer=null,sessionTimeLeft=CONFIG.sessionTimeoutMinutes*60,currentUser=null,pendingAction=null,legacyUserId=null,registeredUsers=[];

function t(k){return(T[currentLang]||T.de)[k]||k}

function checkLegacyData(){
    const oldHuman=localStorage.getItem('windi_human');
    const oldUserId=localStorage.getItem('windi_user_id');
    if(oldHuman||oldUserId){
        legacyUserId=oldUserId;
        document.getElementById('migrationNotice').style.display='block';
        if(oldHuman){try{const p=JSON.parse(oldHuman);document.getElementById('loginFullName').value=p.name||'';document.getElementById('loginDepartment').value=p.dept||'';document.getElementById('loginPosition').value=p.role||''}catch(e){}}
    }
}

function resetSessionTimer(){sessionTimeLeft=CONFIG.sessionTimeoutMinutes*60;updateTimerDisplay()}
function updateTimerDisplay(){const m=Math.floor(sessionTimeLeft/60),s=sessionTimeLeft%60;document.getElementById('sessionTimeLeft').textContent=m+':'+(s<10?'0':'')+s;document.getElementById('sessionTimer').classList.toggle('warning',sessionTimeLeft<=CONFIG.warningTimeSeconds)}
function startSessionTimer(){if(sessionTimer)clearInterval(sessionTimer);sessionTimer=setInterval(function(){sessionTimeLeft--;updateTimerDisplay();if(sessionTimeLeft<=0)handleSessionExpired()},1000)}
function handleSessionExpired(){clearInterval(sessionTimer);sessionId=null;currentUser=null;toast('Sitzung abgelaufen','warning');showLogin()}
['mousedown','keydown','scroll','touchstart'].forEach(function(e){document.addEventListener(e,function(){if(sessionId)resetSessionTimer()})});

function showLogin(){document.getElementById('loginOverlay').style.display='flex';document.getElementById('appContent').style.display='none';document.getElementById('sessionBar').style.display='none'}

function showApp(){
    document.getElementById('loginOverlay').style.display='none';
    document.getElementById('appContent').style.display='flex';
    document.getElementById('sessionBar').style.display='flex';
    document.getElementById('sessionUserName').textContent=currentUser.full_name;
    document.getElementById('sessionUserId').textContent=currentUser.employee_id;
    document.getElementById('fieldAuthorName').value=currentUser.full_name;
    document.getElementById('fieldAuthorId').value=currentUser.employee_id;
    document.getElementById('fieldDate').value=new Date().toISOString().split('T')[0];
}

async function handleLogin(e){
    e.preventDefault();
    const data={full_name:document.getElementById('loginFullName').value,employee_id:document.getElementById('loginEmployeeId').value,department:document.getElementById('loginDepartment').value,position:document.getElementById('loginPosition').value,email:document.getElementById('loginEmail').value,password:document.getElementById('loginPassword').value,supervisor_id:document.getElementById('loginSupervisorId').value,supervisor_name:document.getElementById('loginSupervisorName').value};
    try{
        const res=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
        const result=await res.json();
        if(res.ok&&result.success){
            sessionId=result.session_id;
            currentUser=result.user;
            if(legacyUserId&&legacyUserId!==currentUser.employee_id){await migrateOldDocuments(legacyUserId,currentUser.employee_id,currentUser.full_name)}
            showApp();startSessionTimer();loadDocs();toast('Anmeldung erfolgreich','success');loadWitnessList()
        }else{toast(result.error||'Fehler','error')}
    }catch(err){toast('Verbindungsfehler','error')}
}

async function migrateOldDocuments(oldId,newId,userName){
    try{
        const res=await fetch('/api/migrate/claim-documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_user_id:oldId,new_employee_id:newId,new_user_name:userName})});
        const result=await res.json();
        if(result.migrated>0){toast(result.migrated+' Dokumente migriert','success');localStorage.removeItem('windi_user_id');localStorage.removeItem('windi_human')}
    }catch(e){}
}

async function handleLogout(){
    if(sessionId)try{await fetch('/api/auth/logout',{method:'POST',headers:{'X-Session-ID':sessionId}})}catch(e){}
    clearInterval(sessionTimer);sessionId=null;currentUser=null;showLogin();toast('Abgemeldet','success')
}

function showReauth(action,cb){pendingAction={action:action,callback:cb};document.getElementById('reauthPassword').value='';document.getElementById('reauthOverlay').classList.add('show');document.getElementById('reauthPassword').focus()}
function hideReauth(){pendingAction=null;document.getElementById('reauthOverlay').classList.remove('show')}

async function confirmReauth(){
    const pw=document.getElementById('reauthPassword').value;
    if(!pw)return toast('Passwort erforderlich','error');
    try{
        const res=await fetch('/api/auth/reauth',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify({password:pw,action:pendingAction?pendingAction.action:''})});
        if(res.ok){const cb=pendingAction?pendingAction.callback:null;hideReauth();if(cb)cb()}
        else{const r=await res.json();toast(r.error||'Fehler','error')}
    }catch(e){toast('Fehler','error')}
}

// v4.7-gov: Profile Functions
async function showProfile(){
    try{
        const res=await fetch('/api/auth/profile',{headers:{'X-Session-ID':sessionId}});
        if(res.ok){
            const data=await res.json();
            document.getElementById('profileFullName').value=data.full_name||'';
            document.getElementById('profileEmployeeId').value=data.employee_id||'';
            document.getElementById('profileDepartment').value=data.department||'';
            document.getElementById('profilePosition').value=data.position||'';
            document.getElementById('profileEmail').value=data.email||'';
            document.getElementById('profileSupervisorId').value=data.supervisor_id||'';
            document.getElementById('profileSupervisorName').value=data.supervisor_name||'';
            document.getElementById('profileOverlay').classList.add('show');
        }else{toast('Fehler beim Laden','error')}
    }catch(e){toast('Verbindungsfehler','error')}
}

function hideProfile(){document.getElementById('profileOverlay').classList.remove('show')}

async function saveProfile(){
    const data={
        department:document.getElementById('profileDepartment').value,
        position:document.getElementById('profilePosition').value,
        email:document.getElementById('profileEmail').value,
        supervisor_id:document.getElementById('profileSupervisorId').value,
        supervisor_name:document.getElementById('profileSupervisorName').value
    };
    try{
        const res=await fetch('/api/auth/profile',{method:'PUT',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify(data)});
        if(res.ok){
            const result=await res.json();
            currentUser.department=data.department;
            currentUser.position=data.position;
            currentUser.email=data.email;
            hideProfile();
            toast('Profil gespeichert','success');
        }else{const r=await res.json();toast(r.error||'Fehler','error')}
    }catch(e){toast('Verbindungsfehler','error')}
}

// v4.7-gov: Preview Functions
function showPreview(){
    if(!window._lastLLM){toast('Keine Antwort zum Vorschauen','warning');return}
    document.getElementById('previewContent').innerHTML=window._lastLLM.split('\n').join('<br>');
    document.getElementById('previewOverlay').classList.add('show');
}

function hidePreview(){document.getElementById('previewOverlay').classList.remove('show')}

function confirmInsert(){
    if(window._lastLLM){
        var ed=document.getElementById('editor');var body=ed.querySelector('.body');if(body){body.innerHTML=window._lastLLM.split('\n').join('<br>')}else{ed.innerHTML=window._lastLLM.split('\n').join('<br>')};
        toast('Eingefuegt','success');
        window._lastLLM=null;
    }
    hidePreview();
}

async function loadWitnessList(){
    try{
        const res=await fetch('/api/users',{headers:{'X-Session-ID':sessionId}});
        if(res.ok){
            const data=await res.json();
            registeredUsers=data.users||[];
            const dl=document.getElementById('witnessList');
            dl.innerHTML=registeredUsers.filter(function(u){return u.employee_id!==currentUser.employee_id}).map(function(u){return '<option value="'+u.full_name+'" data-id="'+u.employee_id+'" data-pos="'+(u.position||'')+'">'}).join('');
        }
    }catch(e){}
}

function fillWitnessData(name){
    const user=registeredUsers.find(function(u){return u.full_name===name});
    if(user){
        document.getElementById('fieldWitnessId').value=user.employee_id||'';
        document.getElementById('fieldWitnessPosition').value=user.position||'';
    }
}

function getAuthorData(){return{id:currentUser?currentUser.employee_id:'',name:currentUser?currentUser.full_name:'',employee_id:currentUser?currentUser.employee_id:'',department:currentUser?currentUser.department:'',position:currentUser?currentUser.position:''}}
function getWitnessData(){return{name:document.getElementById('fieldWitnessName').value,id:document.getElementById('fieldWitnessId').value,position:document.getElementById('fieldWitnessPosition').value,relation:document.getElementById('fieldWitnessRelation').value}}

async function newDoc(){
    const res=await fetch('/api/document',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify({language:currentLang,author_data:getAuthorData()})});
    const doc=await res.json();
    docId=doc.id;
    document.getElementById('docTitle').value=doc.title;
    document.getElementById('editor').innerHTML='';
    document.getElementById('fieldDate').value=new Date().toISOString().split('T')[0];
    ['fieldWitnessName','fieldWitnessId','fieldWitnessPosition'].forEach(function(id){document.getElementById(id).value=''});
    document.getElementById('fieldWitnessRelation').value='';
    updateStatus('draft');
    document.getElementById('receiptBox').classList.remove('show');
    loadDocs();
    toast('Erstellt','success');
}

async function saveDoc(){
    if(!docId)await newDoc();
    const content={text:document.getElementById('editor').innerText,html:document.getElementById('editor').innerHTML};
    const res=await fetch('/api/document/'+docId,{method:'PUT',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify({title:document.getElementById('docTitle').value,content:content,human_fields:{author:currentUser?currentUser.full_name:'',author_id:currentUser?currentUser.employee_id:'',date:document.getElementById('fieldDate').value,witness_name:getWitnessData().name,witness_id:getWitnessData().id},author_data:getAuthorData(),witness_data:getWitnessData()})});
    if(res.ok){updateStatus('validated');toast('Gespeichert','success');loadDocs()}
}

async function finalizeDoc(){
    if(!docId)return toast('Kein Dokument','error');
    const wd=getWitnessData();
    if(!wd.name){toast(t('witness_required'),'error');document.getElementById('settingsPanel').classList.remove('collapsed');document.getElementById('fieldWitnessName').focus();return}
    showReauth('FINALIZE',async function(){
        await saveDoc();
        const res=await fetch('/api/document/'+docId+'/finalize',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify({author_data:getAuthorData(),witness_data:wd,language:currentLang})});
        const data=await res.json();
        if(data.receipt){
            updateStatus('finalized');
            const box=document.getElementById('receiptBox');
            box.innerHTML='<strong>'+data.receipt.receipt_id+'</strong><br>Hash: '+data.receipt.hash+'<br>Autor: '+(data.receipt.author?data.receipt.author.name:'-')+'<br>Pruefer: '+(data.receipt.witness?data.receipt.witness.name:'-');
            box.classList.add('show');
            toast('WINDI-QUITTUNG erstellt','success');
        }else if(data.error){toast(data.error,'error')}
    });
}

async function deleteCurrentDoc(){
    if(!docId)return;
    if(!confirm('Dokument loeschen?'))return;
    showReauth('DELETE',async function(){await fetch('/api/document/'+docId,{method:'DELETE',headers:{'X-Session-ID':sessionId}});loadDocs();toast('Geloescht','success')});
}

async function loadDoc(id){
    const res=await fetch('/api/document/'+id,{headers:{'X-Session-ID':sessionId}});
    const doc=await res.json();
    docId=doc.id;
    document.getElementById('docTitle').value=doc.title;
    document.getElementById('editor').innerHTML=doc.content&&doc.content.html?doc.content.html:(doc.content&&doc.content.text?doc.content.text.split('\n').join('<br>'):'');
    document.getElementById('fieldDate').value=doc.human_fields?doc.human_fields.date||'':'';
    document.getElementById('fieldWitnessName').value=doc.human_fields?doc.human_fields.witness_name||'':'';
    document.getElementById('fieldWitnessId').value=doc.human_fields?doc.human_fields.witness_id||'':'';
    updateStatus(doc.status);
    if(doc.receipt){const box=document.getElementById('receiptBox');box.innerHTML='<strong>'+doc.receipt.receipt_id+'</strong><br>Hash: '+doc.receipt.hash;box.classList.add('show')}
    else{document.getElementById('receiptBox').classList.remove('show')}
}

async function loadDocs(){
    const res=await fetch('/api/documents',{headers:{'X-Session-ID':sessionId}});
    const data=await res.json();
    document.getElementById('docList').innerHTML=data.documents.map(function(d){return '<div class="doc-item"><span onclick="loadDoc(\''+d.id+'\')">'+(d.status==='finalized'?'✅':d.status==='validated'?'✓':'📝')+' '+d.title+'</span><button class="doc-item-delete" onclick="event.stopPropagation();deleteDocById(\''+d.id+'\')">✕</button></div>'}).join('');
}

async function deleteDocById(id){
    if(!confirm('Loeschen?'))return;
    const targetId=id;
    showReauth('DELETE',async function(){
        const res=await fetch('/api/document/'+targetId,{method:'DELETE',headers:{'X-Session-ID':sessionId}});
        if(res.ok){loadDocs();if(docId===targetId)newDoc();toast('Geloescht','success')}
        else{toast('Fehler beim Loeschen','error')}
    });
}

function exportDoc(fmt){if(!docId)return toast('Zuerst speichern','error');window.location.href='/api/document/'+docId+'/export/'+fmt}
function updateStatus(s){const b=document.getElementById('statusBadge');b.className='status-badge status-'+s;b.textContent=t(s)}
function execCmd(c,v){document.execCommand(c,false,v||null);document.getElementById('editor').focus()}

async function sendChat(){
    const input=document.getElementById('chatInput'),msg=input.value.trim();
    if(!msg)return;
    const box=document.getElementById('chatMessages');
    box.innerHTML+='<div class="chat-msg chat-user">'+msg.split('\n').join('<br>')+'</div>';
    input.value='';
    box.innerHTML+='<div class="chat-msg chat-ai" id="thinking"><i class="fas fa-spinner fa-spin"></i> ...</div>';
    box.scrollTop=box.scrollHeight;
    try{
        const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Session-ID':sessionId},body:JSON.stringify({message:msg,context:document.getElementById('editor').innerText,dragon:'claude',lang:currentLang})});
        const data=await res.json();
        var thinking=document.getElementById('thinking');if(thinking)thinking.remove();
        if(data.response){
            const fullResp=data.response;
            const isLong=fullResp.length>500;
            const displayHtml=fullResp.split('\n').join('<br>');
            window._lastLLM=fullResp;
            box.innerHTML+='<div class="chat-msg chat-ai"><div class="chat-content'+(isLong?' collapsed':'')+'">'+displayHtml+'</div>'+(isLong?'<button class="expand-btn" onclick="toggleExpand(this)">Mehr anzeigen ▼</button>':'')+'<button class="preview-btn" onclick="showPreview()"><i class="fas fa-eye"></i> Vorschau</button><button class="insert-btn" onclick="confirmInsert()"><i class="fas fa-plus"></i> Einfuegen</button></div>';
        }
    }catch(e){var thinking=document.getElementById('thinking');if(thinking)thinking.remove();box.innerHTML+='<div class="chat-msg chat-ai" style="color:var(--danger)">Fehler</div>'}
    box.scrollTop=box.scrollHeight;
}

function sendDocToChat(){if(!docId)return toast('Kein Dokument','error');document.getElementById('chatInput').value='Bitte ueberarbeiten:';document.getElementById('chatInput').focus()}

function toggleExpand(btn){
    const content=btn.previousElementSibling;
    if(content.classList.contains('collapsed')){content.classList.remove('collapsed');btn.textContent='Weniger anzeigen ▲'}
    else{content.classList.add('collapsed');btn.textContent='Mehr anzeigen ▼'}
}

function toggleSidebar(){document.getElementById('sidebar').classList.toggle('collapsed')}
function togglePanel(){document.getElementById('settingsPanel').classList.toggle('collapsed')}
function setLang(l){
  currentLang=l;
  document.querySelectorAll('.lang-btn').forEach(function(b){b.classList.toggle('active',b.dataset.lang===l)});
  applyTranslations(l);
}

var _translations=null;
function applyTranslations(lang){
  if(!_translations){
    fetch('/api/translations').then(r=>r.json()).then(function(data){
      _translations=data;
      _doTranslate(lang);
    }).catch(function(){});
    return;
  }
  _doTranslate(lang);
}

function _doTranslate(lang){
  var tr=_translations[lang]||_translations['de']||{};
  var de=_translations['de']||{};
  function g(k){return tr[k]||de[k]||k}

  // Sidebar
  var newBtn=document.querySelector('.btn-new');
  if(newBtn) newBtn.innerHTML='<i class="fas fa-plus"></i> '+g('new_doc');

  // Top bar buttons
  var saveBtn=document.querySelector('.btn-save');
  if(saveBtn) saveBtn.innerHTML='<i class="fas fa-save"></i> '+g('save');
  var finBtn=document.querySelector('.btn-finalize');
  if(finBtn) finBtn.innerHTML='<i class="fas fa-check"></i> '+(tr['finalize']||de['finalize']||'Abschließen');

  // Status badge
  var badge=document.getElementById('statusBadge');
  if(badge){
    if(badge.classList.contains('status-draft')) badge.textContent=g('draft');
    else if(badge.classList.contains('status-validated')) badge.textContent=g('validated');
    else if(badge.classList.contains('status-finalized')) badge.textContent=g('finalized');
  }

  // Editor placeholder
  var titleInput=document.getElementById('docTitle');
  if(titleInput && (!titleInput.value || titleInput.value==='Neues Dokument' || titleInput.value==='New Document' || titleInput.value==='Novo Documento'))
    titleInput.placeholder=g('title');

  // Chat
  var chatHeader=document.querySelector('.chat-header');
  if(chatHeader) chatHeader.innerHTML='<i class="fas fa-dragon"></i> WINDI LLM Chat';
  var chatInput=document.getElementById('chatInput');
  if(chatInput){
    var placeholders={de:'Nachricht...',en:'Message...',pt:'Mensagem...'};
    chatInput.placeholder=placeholders[lang]||'Nachricht...';
  }
  var sendBtn=document.querySelector('.chat-send');
  if(sendBtn) sendBtn.innerHTML='<i class="fas fa-paper-plane"></i> '+(lang==='de'?'Senden':lang==='en'?'Send':'Enviar');
  var docChatBtn=document.querySelector('.chat-send-doc');
  if(docChatBtn) docChatBtn.innerHTML='<i class="fas fa-file-export"></i> Doc→Chat';

  // Settings panel labels
  var authorTitle=document.querySelector('.panel-title');
  if(authorTitle && authorTitle.textContent.trim().match(/Autor|Author|Autor/))
    authorTitle.innerHTML='<i class="fas fa-user"></i> '+g('author');

  // Witness section
  var witnessLabels={de:'Prüfer',en:'Reviewer',pt:'Revisor'};
  var witnessTitles=document.querySelectorAll('.panel-title');
  witnessTitles.forEach(function(el){
    if(el.textContent.match(/Prüfer|Reviewer|Revisor/))
      el.innerHTML='<i class="fas fa-eye"></i> '+(witnessLabels[lang]||'Prüfer');
  });

  // Export section
  witnessTitles.forEach(function(el){
    if(el.textContent.match(/Export/))
      el.innerHTML='<i class="fas fa-file-export"></i> Export';
  });

  // Human only labels
  document.querySelectorAll('.human-field small').forEach(function(el){
    if(el.textContent.match(/Nur Mensch|Human only|Somente humano/))
      el.textContent='\u{1F512} '+g('human_only');
    if(el.textContent.match(/Erforderlich|Required|Obrigatório/))
      el.textContent='\u{1F512} '+(lang==='de'?'Erforderlich':lang==='en'?'Required':'Obrigatório');
  });

  // Login principle
  var principle=document.querySelector('.login-principle');
  if(principle) principle.innerHTML='\u{1F512} '+g('principle');

  // Date label
  var dateLabels={de:'Datum',en:'Date',pt:'Data'};
  document.querySelectorAll('.human-field label').forEach(function(el){
    if(el.textContent.match(/^Datum$|^Date$|^Data$/)) el.textContent=dateLabels[lang]||'Datum';
    if(el.textContent.match(/^Name/)) el.textContent='Name';
  });

  // Witness relation options
  var relSelect=document.getElementById('fieldWitnessRelation');
  if(relSelect){
    var opts={
      de:['-- Auswählen --','Vorgesetzter','Compliance','Peer','Extern'],
      en:['-- Select --','Supervisor','Compliance','Peer','External'],
      pt:['-- Selecionar --','Supervisor','Compliance','Par','Externo']
    };
    var o=opts[lang]||opts['de'];
    var options=relSelect.querySelectorAll('option');
    if(options.length>=5){options[0].textContent=o[0];options[1].textContent=o[1];options[2].textContent=o[2];options[3].textContent=o[3];options[4].textContent=o[4]}
  }

  // Chat welcome message (only first message)
  var firstMsg=document.querySelector('.chat-msg.chat-ai');
  if(firstMsg){
    var welcomes={de:'Willkommen! Wie kann ich helfen?',en:'Welcome! How can I help?',pt:'Bem-vindo! Como posso ajudar?'};
    if(firstMsg.textContent.match(/Willkommen|Welcome|Bem-vindo/))
      firstMsg.textContent=welcomes[lang]||welcomes['de'];
  }

  // Login form (if visible)
  var loginHeader=document.querySelector('.login-header p');
  if(loginHeader){
    var cards={de:'Human Identity Card',en:'Human Identity Card',pt:'Cartão de Identidade Humana'};
    loginHeader.textContent=cards[lang]||cards['de'];
  }

  // Profile modal
  var profileH3=document.querySelector('.profile-modal h3');
  if(profileH3){
    var titles={de:'Mein Profil',en:'My Profile',pt:'Meu Perfil'};
    profileH3.innerHTML='<i class="fas fa-user-edit"></i> '+(titles[lang]||titles['de']);
  }
}
function initLangBar(){document.getElementById('langBar').innerHTML=Object.keys(LANGS).map(function(k){return '<button class="lang-btn '+(k===currentLang?'active':'')+'" data-lang="'+k+'" onclick="setLang(\''+k+'\')">'+LANGS[k].flag+'</button>'}).join('')}
function toast(m,t){var el=document.createElement('div');el.className='toast toast-'+t;el.textContent=m;document.body.appendChild(el);setTimeout(function(){el.remove()},3000)}

document.addEventListener('DOMContentLoaded',function(){
    document.getElementById('chatInput').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}});
    document.getElementById('reauthPassword').addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();confirmReauth()}});
});

function cleanLLMResponse(text){
    var lines=text.split('\n');
    var clean=[];
    var skip=['Human decides','WINDI Publishing','KI verarbeitet','EU AI Act','A4 Desk BABEL','Dokument wurde von menschlichen','human supervision'];
    for(var i=0;i<lines.length;i++){
        var dominated=false;
        for(var j=0;j<skip.length;j++){if(lines[i].indexOf(skip[j])>=0){dominated=true;break}}
        if(!dominated)clean.push(lines[i]);
    }
    return clean.join('\n').replace(/^[\s\-]*$/gm,'').replace(/\n{3,}/g,'\n\n');
}
let selectedTemplateId=null;
let selectedIspId=null;
let ispProfiles=[];

async function loadISPTemplates(){
    try{
        const res=await fetch("/api/templates/available");
        const data=await res.json();
        ispProfiles=data.profiles||[];
        const grid=document.getElementById("templateGrid");

        if(ispProfiles.length===0){
            grid.innerHTML='<p style="text-align:center;color:#718096;">Keine ISP Profile verfügbar</p>';
            return;
        }

        let html='<div class="isp-selector" style="margin-bottom:20px;">';
        html+='<label style="font-weight:600;display:block;margin-bottom:8px;"><i class="fas fa-building"></i> Institution auswählen:</label>';
        html+='<select id="ispSelect" onchange="onIspSelect(this.value)" style="width:100%;padding:10px;border:2px solid #e2e8f0;border-radius:8px;font-size:1rem;">';
        html+='<option value="">-- Bitte wählen --</option>';
        ispProfiles.forEach(p=>{
            html+='<option value="'+p.id+'" data-color="'+p.primary_color+'">'+p.name+' ('+p.jurisdiction+')</option>';
        });
        html+='</select></div>';
        html+='<div id="ispTemplateList"></div>';
        grid.innerHTML=html;
    }catch(e){
        console.error("ISP Load error:",e);
        document.getElementById("templateGrid").innerHTML='<p style="color:#e53e3e;">Fehler beim Laden der ISP Profile</p>';
    }
}

function onIspSelect(ispId){
    selectedIspId=ispId;
    selectedTemplateId=null;
    const list=document.getElementById("ispTemplateList");

    if(!ispId){
        list.innerHTML='';
        return;
    }

    const profile=ispProfiles.find(p=>p.id===ispId);
    if(!profile){
        list.innerHTML='<p>Profil nicht gefunden</p>';
        return;
    }

    let html='<div style="margin-top:15px;">';

    // Forms section
    if(profile.forms&&profile.forms.length>0){
        html+='<div style="margin-bottom:15px;"><label style="font-weight:600;color:#1a365d;display:block;margin-bottom:10px;"><i class="fas fa-file-alt"></i> Formulare:</label>';
        html+='<div class="template-grid">';
        profile.forms.forEach(f=>{
            const formTitle=f.replace(/-/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
            html+='<div class="template-card" data-type="form" data-id="'+f+'" onclick="selectISPTemplate(this,\'form\',\''+f+'\')">';
            html+='<div class="template-card-header" style="background:linear-gradient(135deg,'+profile.primary_color+',#2c5282)"></div>';
            html+='<div class="template-card-name">'+formTitle+'</div>';
            html+='<div class="template-card-desc">'+profile.short_name+' Formular</div>';
            html+='<div class="template-card-langs"><span class="template-card-lang">'+profile.governance_level+'</span></div>';
            html+='</div>';
        });
        html+='</div></div>';
    }

    // Templates section
    if(profile.templates&&profile.templates.length>0){
        html+='<div><label style="font-weight:600;color:#1a365d;display:block;margin-bottom:10px;"><i class="fas fa-file-invoice"></i> Templates:</label>';
        html+='<div class="template-grid">';
        profile.templates.forEach(t=>{
            const tplTitle=t.replace(/-/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
            html+='<div class="template-card" data-type="template" data-id="'+t+'" onclick="selectISPTemplate(this,\'template\',\''+t+'\')">';
            html+='<div class="template-card-header" style="background:linear-gradient(135deg,'+profile.primary_color+',#4a5568)"></div>';
            html+='<div class="template-card-name">'+tplTitle+'</div>';
            html+='<div class="template-card-desc">'+profile.short_name+' Template</div>';
            html+='<div class="template-card-langs"><span class="template-card-lang">'+profile.governance_level+'</span></div>';
            html+='</div>';
        });
        html+='</div></div>';
    }

    if((!profile.forms||profile.forms.length===0)&&(!profile.templates||profile.templates.length===0)){
        html+='<p style="text-align:center;color:#718096;padding:20px;">Keine Templates oder Formulare für dieses Profil verfügbar.</p>';
    }

    html+='</div>';
    list.innerHTML=html;
}

function selectISPTemplate(el,type,id){
    document.querySelectorAll(".template-card").forEach(c=>c.classList.remove("selected"));
    el.classList.add("selected");
    selectedTemplateId={type:type,id:id,isp:selectedIspId};
}

async function applySelectedTemplate(){
    if(!selectedTemplateId||!selectedIspId){
        return toast("Bitte ISP und Template auswählen","warning");
    }

    try{
        const endpoint=selectedTemplateId.type==='form'
            ? '/api/templates/isp/'+selectedIspId+'/form/'+selectedTemplateId.id
            : '/api/templates/isp/'+selectedIspId+'/template/'+selectedTemplateId.id;

        const res=await fetch(endpoint);
        const data=await res.json();

        if(data.html){
            // Create iframe-like container for the form
            const editor=document.getElementById("editor");
            editor.innerHTML='<div class="isp-document" style="background:#fff;padding:0;margin:0;">'+data.html+'</div>';

            // Update document metadata
            if(window.currentDocMetadata){
                window.currentDocMetadata.institutional_profile=selectedIspId;
                window.currentDocMetadata.template_type=selectedTemplateId.type;
                window.currentDocMetadata.form_id=selectedTemplateId.type==='form'?selectedTemplateId.id:null;
            }

            if(window.WINDI_TOOLBAR)window.WINDI_TOOLBAR.setCurrentTemplate(selectedTemplateId.id);

            // Update title
            const title=selectedTemplateId.id.replace(/-/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
            document.getElementById("docTitle").value=title;

            toast("ISP Template angewendet: "+title,"success");
            hideTemplateModal();
        }else{
            toast(data.error||"Fehler beim Laden","error");
        }
    }catch(e){
        console.error("Template apply error:",e);
        toast("Fehler beim Anwenden","error");
    }
}

// Legacy function for old templates (still supported)
async function loadTemplates(){
    try{
        const res=await fetch("/api/registry/templates/visual");
        if(res.ok){
            const data=await res.json();
            if(data.templates&&data.templates.length>0){
                // Old template system still works
                const grid=document.getElementById("templateGrid");
                const existingContent=grid.innerHTML;
                grid.innerHTML=existingContent+'<div style="margin-top:20px;padding-top:15px;border-top:1px solid #e2e8f0;"><label style="font-weight:600;color:#718096;display:block;margin-bottom:10px;">Legacy Templates:</label><div class="template-grid">'+data.templates.map(t=>'<div class="template-card" data-id="'+t.id+'" onclick="selectTemplate(this,\''+t.id+'\')"><div class="template-card-header" style="background:linear-gradient(135deg,'+(t.colors?t.colors.primary:'#718096')+','+(t.colors?t.colors.secondary||t.colors.primary:'#4a5568')+')"></div><div class="template-card-name">'+t.name+'</div><div class="template-card-desc">'+(t.description||'')+'</div></div>').join("")+'</div></div>';
            }
        }
    }catch(e){
        // Legacy templates not available, that's OK
    }
}

function selectTemplate(el,id){
    document.querySelectorAll(".template-card").forEach(c=>c.classList.remove("selected"));
    el.classList.add("selected");
    selectedTemplateId={type:'legacy',id:id};
}

function showTemplateModal(){
    document.getElementById("templateOverlay").classList.add("show");
    selectedTemplateId=null;
    selectedIspId=null;
    loadISPTemplates().then(()=>loadTemplates());
}

function hideTemplateModal(){
    document.getElementById("templateOverlay").classList.remove("show");
    selectedTemplateId=null;
    selectedIspId=null;
}initLangBar();
checkLegacyData();

// === BYPASS AUTH FOR TESTING ===
function autoLoginForTesting(){
    sessionId='TEST-SESSION-'+Date.now();
    currentUser={employee_id:'TEST-001',full_name:'Test User',department:'Development',position:'Tester'};
    document.getElementById('loginOverlay').style.display='none';
    document.getElementById('appContent').style.display='flex';
    document.getElementById('sessionBar').style.display='flex';
    document.getElementById('sessionUserName').textContent=currentUser.full_name;
    document.getElementById('sessionUserId').textContent=currentUser.employee_id;
    document.getElementById('fieldAuthorName').value=currentUser.full_name;
    document.getElementById('fieldAuthorId').value=currentUser.employee_id;
    document.getElementById('fieldDate').value=new Date().toISOString().split('T')[0];
    toast('⚠️ Modo de Teste - Auth Desabilitada','warning');
    console.log('AUTH BYPASS: Test mode enabled');
}
autoLoginForTesting();
// === END BYPASS ===
</script>
<script src="/static/extensions/institutional_blocks.js"></script>
<script src="/static/toolbar/institutional_toolbar.js"></script>
<script src="/static/governance-editor.js"></script>
</body></html>'''

# === Governance API Proxy (added by dashboard deploy) ===
@app.route('/api/gov/<path:endpoint>', methods=['GET', 'POST', 'OPTIONS'])
def governance_proxy(endpoint):
    """Proxy requests to Governance API on localhost:8080"""
    target = f"http://localhost:8080/api/{endpoint}"
    try:
        if request.method == 'GET':
            resp = requests.get(target, timeout=5)
        elif request.method == 'POST':
            resp = requests.post(target, json=request.get_json(silent=True), timeout=5)
        else:
            return '', 204
        return (resp.content, resp.status_code, {'Content-Type': 'application/json'})
    except Exception as e:
        return jsonify({"error": f"Governance API unavailable: {str(e)}"}), 502
# === END Governance API Proxy ===


# === Evolution API Proxy (Phase 2.0) ===
@app.route('/api/evolution/<path:endpoint>', methods=['GET', 'POST', 'OPTIONS'])
def evolution_proxy(endpoint):
    """Proxy requests to Evolution API on localhost:8083"""
    target = f"http://localhost:8083/api/governance/{endpoint}"
    try:
        if request.method == 'GET':
            resp = requests.get(target, timeout=10)
        elif request.method == 'POST':
            resp = requests.post(target, json=request.get_json(silent=True), timeout=10)
        else:
            return '', 204
        return (resp.content, resp.status_code, {
            'Content-Type': 'application/json',
            'X-WINDI-Source': 'evolution-api'
        })
    except Exception as e:
        return jsonify({"error": f"Evolution API unavailable: {str(e)}"}), 502
# === END Evolution API Proxy ===

if __name__ == '__main__':
    print("🏛️ A4 Desk BABEL v4.7-gov")
    print("✅ NEW: Mein Profil - Edit your profile data")
    print("✅ NEW: Preview before Insert")
    print("✅ NEW: Human Authorship Notice in PDF")
    print("URL: http://0.0.0.0:8085")
    app.run(host='0.0.0.0', port=CONFIG["port"], debug=False)
