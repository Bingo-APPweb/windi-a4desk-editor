"""
WINDI Governance Bridge v1.1 — a4Desk BABEL → Governance API
=============================================================
Created: 05 Feb 2026
Updated: 05 Feb 2026 (v1.1 — Architect Dragon review)

v1.1 Changes:
  + Dedicated log: /var/log/windi/governance_bridge.log
  + Correlation ID (GBR-BRIDGE-YYYYMMDD-XXXX) per submission
  + Throttle: 200ms between submissions (flood protection)
  + Failed attempts logged as governance evidence (intent proof)
  + get_failed_submissions() for audit queries

Safety:
  - Bridge errors NEVER break BABEL finalize
  - If Governance API is down, BABEL still works
  - Failed attempts are EVIDENCE of governance intent

"AI processes. Human decides. WINDI guarantees."
"""

import json
import hashlib
import logging
import logging.handlers
import os
import time
import threading
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GOVERNANCE_API_URL = "http://127.0.0.1:8080/api/generate"
BRIDGE_VERSION = "1.1.0"
TIMEOUT_SECONDS = 10
THROTTLE_SECONDS = 0.2  # Flood protection: min 200ms between submits
LOG_DIR = "/var/log/windi"
LOG_FILE = os.path.join(LOG_DIR, "governance_bridge.log")
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB per file
LOG_BACKUP_COUNT = 5  # Keep 5 rotated logs

# ═══════════════════════════════════════════════════════════════
# DEDICATED LOGGER — Governance evidence trail
# ═══════════════════════════════════════════════════════════════

_bridge_logger = logging.getLogger("windi.governance_bridge")
_bridge_logger.setLevel(logging.DEBUG)
_bridge_logger.propagate = False  # Don't duplicate to root logger

# Ensure log directory exists
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except PermissionError:
    LOG_DIR = "/tmp"
    LOG_FILE = os.path.join(LOG_DIR, "governance_bridge.log")

# File handler with rotation (THE governance evidence file)
try:
    _file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [BRIDGE] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _bridge_logger.addHandler(_file_handler)
except Exception:
    pass

# Console handler (goes to /tmp/a4desk.log via nohup)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter(
    "[BRIDGE][%(levelname)s] %(message)s"
))
_bridge_logger.addHandler(_console_handler)

# ═══════════════════════════════════════════════════════════════
# THROTTLE — Prevent flood (governance must be stable, not nervous)
# ═══════════════════════════════════════════════════════════════

_last_submit_time = 0.0
_throttle_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════
# CORRELATION ID GENERATOR
# Chain of custody: Document → Bridge → API → Ledger → War Room
# ═══════════════════════════════════════════════════════════════

_daily_counter = 0
_daily_counter_date = ""
_counter_lock = threading.Lock()


def _generate_correlation_id():
    """
    Generate unique Bridge Correlation ID.
    Format: GBR-BRIDGE-YYYYMMDD-XXXX (sequential per day, resets at midnight UTC)
    """
    global _daily_counter, _daily_counter_date

    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    with _counter_lock:
        if today != _daily_counter_date:
            _daily_counter = 0
            _daily_counter_date = today
        _daily_counter += 1
        seq = _daily_counter

    return f"GBR-BRIDGE-{today}-{seq:04d}"


# ═══════════════════════════════════════════════════════════════
# MAIN SUBMIT FUNCTION
# ═══════════════════════════════════════════════════════════════

def submit_to_governance(doc_id, content_text, language, author_data,
                         witness_data, receipt, domain_tag="operational",
                         governance_level=None):
    """
    Submit a finalized document to the Governance API.

    NEVER raises exceptions — BABEL must not break.
    Failed attempts are logged as governance evidence (intent proof).

    Returns:
        dict with submission result + correlation_id, or None on failure
    """
    correlation_id = _generate_correlation_id()
    start_time = time.time()

    try:
        # ─── THROTTLE ─────────────────────────────────────────
        global _last_submit_time
        with _throttle_lock:
            elapsed = time.time() - _last_submit_time
            if elapsed < THROTTLE_SECONDS:
                wait = THROTTLE_SECONDS - elapsed
                _bridge_logger.debug(
                    f"THROTTLE doc_id={doc_id} corr={correlation_id} "
                    f"wait={wait:.3f}s"
                )
                time.sleep(wait)
            _last_submit_time = time.time()

        # ─── AUTO-DETECT LEVEL ─────────────────────────────────
        if governance_level is None:
            governance_level = _detect_level(domain_tag, content_text)

        # ─── BUILD PAYLOAD ─────────────────────────────────────
        content_hash = hashlib.sha256(content_text.encode()).hexdigest()
        receipt_id = receipt.get("receipt_id", "")

        metadata = {
            # Origin tracing (War Room Decision Card)
            "source": "a4desk_babel",
            "bridge_version": BRIDGE_VERSION,
            "bridge_correlation_id": correlation_id,
            # Document identity
            "document_id": doc_id,
            "language": language,
            "domain_tag": domain_tag,
            "content_hash": content_hash,
            "receipt_id": receipt_id,
            # Human actors
            "author_name": author_data.get("name", ""),
            "author_department": author_data.get("department", ""),
            "author_employee_id": author_data.get("employee_id", ""),
            "witness_name": witness_data.get("name", ""),
            "witness_role": witness_data.get("role", "Prüfer"),
            # Timestamps
            "finalized_at": datetime.now(timezone.utc).isoformat(),
        }

        payload = {
            "governance_level": governance_level,
            "document_type": domain_tag,
            "document_id": doc_id,
            "correlation_id": correlation_id,
            "metadata": metadata,
        }

        # ─── LOG ATTEMPT (governance evidence of intent) ────────
        _bridge_logger.info(
            f"SUBMIT_ATTEMPT doc_id={doc_id} corr={correlation_id} "
            f"level={governance_level} domain={domain_tag} "
            f"receipt={receipt_id} hash={content_hash[:12]}"
        )

        # ─── POST TO GOVERNANCE API ────────────────────────────
        req = Request(
            GOVERNANCE_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        elapsed_ms = int((time.time() - start_time) * 1000)
        submission_id = result.get("submission_id", result.get("id", "?"))

        # Inject correlation data into result
        result["bridge_correlation_id"] = correlation_id
        result["bridge_version"] = BRIDGE_VERSION

        _bridge_logger.info(
            f"SUBMIT_SUCCESS doc_id={doc_id} corr={correlation_id} "
            f"submission={submission_id} level={governance_level} "
            f"elapsed={elapsed_ms}ms"
        )

        return result

    except URLError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        _bridge_logger.error(
            f"SUBMIT_FAILED doc_id={doc_id} corr={correlation_id} "
            f"reason=api_unreachable error=\"{e}\" elapsed={elapsed_ms}ms "
            f"level={governance_level} receipt={receipt.get('receipt_id', '')}"
        )
        return None

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        _bridge_logger.error(
            f"SUBMIT_FAILED doc_id={doc_id} corr={correlation_id} "
            f"reason=unexpected error=\"{e}\" elapsed={elapsed_ms}ms "
            f"level={governance_level or 'UNKNOWN'}"
        )
        return None


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE LEVEL AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════

def _detect_level(domain_tag, content_text):
    """Auto-detect governance level from domain and content."""
    HIGH_DOMAINS = {
        "institutional", "regulatory", "financial", "legal",
        "bundesregierung", "deutsche-bahn", "bis-style", "bafin",
    }
    MEDIUM_DOMAINS = {"compliance", "hr", "procurement"}

    if domain_tag in HIGH_DOMAINS:
        return "HIGH"
    if domain_tag in MEDIUM_DOMAINS:
        return "MEDIUM"

    text_lower = content_text.lower() if content_text else ""

    high_kw = [
        "vertraulich", "confidential", "restricted",
        "personenbezogen", "gdpr", "dsgvo", "geheim",
    ]
    medium_kw = [
        "intern", "internal", "entwurf", "draft",
        "bescheid", "antrag", "genehmigung",
    ]

    for kw in high_kw:
        if kw in text_lower:
            return "HIGH"
    for kw in medium_kw:
        if kw in text_lower:
            return "MEDIUM"

    return "LOW"


# ═══════════════════════════════════════════════════════════════
# HEALTH & AUDIT FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def health_check():
    """Quick check if Governance API is reachable."""
    try:
        req = Request("http://127.0.0.1:8080/api/status", method="GET")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "status": "connected",
            "api": data.get("api", "unknown"),
            "bridge_version": BRIDGE_VERSION,
            "log_file": LOG_FILE,
        }
    except Exception as e:
        return {
            "status": "disconnected",
            "error": str(e),
            "bridge_version": BRIDGE_VERSION,
            "log_file": LOG_FILE,
        }


def get_recent_logs(n=20):
    """Return last N lines from bridge log."""
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        return [l.strip() for l in lines[-n:]]
    except Exception:
        return []


def get_failed_submissions(n=50):
    """
    Return recent failed submissions from log.
    This is AUDIT EVIDENCE — proves governance intent
    even when infrastructure failed.
    """
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        return [l.strip() for l in lines if "SUBMIT_FAILED" in l][-n:]
    except Exception:
        return []


def get_submission_stats():
    """Quick stats from log for monitoring."""
    try:
        with open(LOG_FILE, "r") as f:
            content = f.read()
        return {
            "total_attempts": content.count("SUBMIT_ATTEMPT"),
            "total_success": content.count("SUBMIT_SUCCESS"),
            "total_failed": content.count("SUBMIT_FAILED"),
            "total_throttled": content.count("THROTTLE"),
            "log_file": LOG_FILE,
        }
    except Exception:
        return {"error": "Log not readable"}
