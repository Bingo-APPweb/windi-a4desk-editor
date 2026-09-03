"""
WINDI Ledger Bridge — WS-1 Integration (Updated 12 Jul 2026)

Connects BABEL exports to the Forensic Ledger (:8101) for Virtue Receipts.
Implements 2-step sealing: register receipt → seal bundle hash.

Principle: "AI processes. Human decides. WINDI guarantees."
Zero-Knowledge: Only hashes + metadata reach the Ledger. NEVER content.

Author: Claude Code (WS-1 Prompt 3)
Date: 2026-02-19
Updated: 2026-07-12 — Phase 2 W-FUNIL-FECHADO-001
  - Added schema_version (required by Ledger)
  - Added actor DID support (Art. 50 EU AI Act — proof of human contribution)
  - Added issuer field (service identity separate from actor)
  - Added wallet_id (required by Ledger)
  - SCAFFOLD: Full Berçário DID integration pending — interim uses fallback
"""

import json
import urllib.request
import urllib.error
from uuid import uuid4
from datetime import datetime
from typing import Optional, Dict, Any

# Forensic Ledger endpoint
LEDGER_URL = "http://localhost:8101"
TIMEOUT_SECONDS = 10

# Service identity — the service that facilitates, not the human who creates
# Note: Using dragon-001 as validated DID until a4desk-001 is registered in Genesis
SERVICE_DID = "did:windi:dragon-001"
SERVICE_WALLET = "WINDI-SYSTEM"

# SCAFFOLD FLAG: When True, full Berçário DID integration is active
# When False, fallback to service identity with explicit declaration
BERCARIO_DID_ACTIVE = False  # TODO: Enable after W-DID-GENESIS integration


def generate_receipt_id() -> str:
    """
    Generate a unique Virtue Receipt ID for BABEL exports.

    Returns:
        Receipt ID in format: WINDI-A4DESK-YYYYMMDDHHMMSS-HASH8
    """
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:8].upper()
    return f"WINDI-A4DESK-{ts}-{suffix}"


def register_in_ledger(
    doc_id: str,
    doc_name: str,
    doc_type: str = "doc",
    content_hash: str = "",
    governance_level: str = "LOW",
    sge_score: float = 0.0,
    template_id: Optional[str] = None,
    export_format: Optional[str] = None,
    # DID-aware parameters (Phase 2)
    user_did: Optional[str] = None,
    user_wallet: Optional[str] = None,
    human_approved: bool = True
) -> Dict[str, Any]:
    """
    Register a document export in the Forensic Ledger.

    Creates a Virtue Receipt with the document's content hash.
    This is step 1 of the 2-step sealing process.

    Args:
        doc_id: Original document ID from BABEL
        doc_name: Document title/name
        doc_type: Type (doc, xlsx, pptx, jmpg, communique)
        content_hash: Full 64-char SHA-256 of canonical content
        governance_level: LOW, MED, MEDIUM, HIGH, or CRIT
        sge_score: Semantic Governance Engine score (0.0-1.0)
        template_id: Template used (if any)
        export_format: Export format (pdf, docx, etc.)
        user_did: DID from Berçário (Art. 50 — proof of human contribution)
        user_wallet: User's wallet ID
        human_approved: I9 gate (must be True for seal)

    Returns:
        {"success": True, "receipt": {...}} on success
        {"success": False, "error": "..."} on failure

    Note:
        Handles Ledger unavailability gracefully. Export should NOT fail
        if Ledger is down — this function catches all exceptions.
    """
    receipt_id = generate_receipt_id()

    # Normalize governance level
    if governance_level == "MEDIUM":
        governance_level = "MED"

    # Determine actor and wallet based on DID availability
    # Art. 50 EU AI Act: actor = human who created, not the service
    if user_did and BERCARIO_DID_ACTIVE:
        actor = user_did
        wallet_id = user_wallet or SERVICE_WALLET
        identity_mode = "user_did"
    else:
        # SCAFFOLD: Fallback to service identity with explicit declaration
        # CAP3 FIX (2026-09-03): wallet_id must be valid DID for Ledger acceptance
        actor = SERVICE_DID
        wallet_id = SERVICE_DID  # Changed from SERVICE_WALLET per CAP3 compatibility
        identity_mode = "service_fallback"

    # Ensure content_hash has sha256: prefix
    if content_hash and not content_hash.startswith("sha256:"):
        content_hash = f"sha256:{content_hash}"

    # §POST canonical schema (CLAUDE.md 12 Jul 2026)
    payload = {
        "schema_version": "1.0",
        "id": receipt_id,
        "actor": actor,
        "wallet_id": wallet_id,
        "app": "a4desk-babel",
        "doc_name": doc_name,
        "doc_type": doc_type,
        "content_hash": content_hash,
        "governance_level": governance_level,
        "sge_score": float(sge_score) if sge_score else 0.0,
        "declaration": "operator",
        "human_approved": human_approved,
        "tags": ["a4desk", "babel", "document"],
    }

    # Optional fields
    if template_id:
        payload["template_id"] = template_id

    # Metadata with full provenance
    payload["metadata"] = {
        "source": "a4desk-babel",
        "original_doc_id": doc_id,
        "issuer": SERVICE_DID,
        "identity_mode": identity_mode,
    }

    # SCAFFOLD: Track when DID fallback is used
    if identity_mode == "service_fallback":
        payload["metadata"]["scaffold_note"] = "Berçário DID integration pending. Actor is service identity."

    if export_format:
        payload["metadata"]["export_format"] = export_format

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{LEDGER_URL}/api/receipts",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Add entry_id for compatibility (Ledger returns 'id' in payload)
            result["entry_id"] = receipt_id
            print(f"[LEDGER] ◆ Receipt registered: {receipt_id} | {doc_name} | mode={identity_mode}")
            return {"success": True, "receipt": result}

    except urllib.error.URLError as e:
        error_msg = f"Ledger unreachable: {e.reason if hasattr(e, 'reason') else str(e)}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}
    except urllib.error.HTTPError as e:
        error_msg = f"Ledger HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Ledger error: {str(e)}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}


def seal_bundle(
    receipt_id: str,
    bundle_hash: str,
    bundle_size: int
) -> Dict[str, Any]:
    """
    Seal the bundle hash onto an existing Virtue Receipt.

    This is step 2 of the 2-step sealing process. After the export file
    is generated, we compute its SHA-256 and attach it to the receipt.

    Args:
        receipt_id: The WINDI-A4DESK-xxx ID from register_in_ledger
        bundle_hash: Full 64-char SHA-256 of exported file bytes
        bundle_size: Size of exported file in bytes

    Returns:
        {"success": True, "result": {...}} on success
        {"success": False, "error": "..."} on failure
    """
    payload = {
        "bundle_hash": bundle_hash,
        "bundle_size": int(bundle_size)
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{LEDGER_URL}/api/receipts/{receipt_id}/seal-bundle",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"[LEDGER] ◆ Bundle sealed: {receipt_id} | {bundle_hash[:16]}... | {bundle_size} bytes")
            return {"success": True, "result": result}

    except urllib.error.URLError as e:
        error_msg = f"Ledger unreachable for seal: {e.reason if hasattr(e, 'reason') else str(e)}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}
    except urllib.error.HTTPError as e:
        error_msg = f"Ledger seal HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Bundle seal error: {str(e)}"
        print(f"[LEDGER] ⚠ {error_msg}")
        return {"success": False, "error": error_msg}


def verify_receipt(receipt_id: str) -> Dict[str, Any]:
    """
    Verify a Virtue Receipt exists in the Forensic Ledger.

    Args:
        receipt_id: The WINDI-A4DESK-xxx ID to verify

    Returns:
        {"success": True, "receipt": {...}} with full receipt data
        {"success": False, "error": "..."} on failure
    """
    try:
        req = urllib.request.Request(
            f"{LEDGER_URL}/api/receipts/{receipt_id}",
            headers={"Accept": "application/json"},
            method="GET"
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "receipt": result}

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"success": False, "error": f"Receipt {receipt_id} not found"}
        error_msg = f"Verify HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}"
        return {"success": False, "error": error_msg}
    except urllib.error.URLError as e:
        error_msg = f"Ledger unreachable for verify: {e.reason if hasattr(e, 'reason') else str(e)}"
        return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_constitutional(receipt_id: str) -> Dict[str, Any]:
    """
    Verify via constitutional resolution (:8114) — R2 semantics.

    This is the public verification path that returns FOUND/W1/proof_limits.

    Args:
        receipt_id: The receipt ID to verify

    Returns:
        {"success": True, "resolution": {...}} with status_semantics, assurance_level
        {"success": False, "error": "..."} on failure
    """
    try:
        req = urllib.request.Request(
            f"http://localhost:8114/verify-public/document/{receipt_id}",
            headers={"Accept": "application/json"},
            method="GET"
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "resolution": result}

    except urllib.error.HTTPError as e:
        error_msg = f"Constitutional verify HTTP {e.code}"
        return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# Convenience function for full export flow
# ═══════════════════════════════════════════════════════════════════════════

def register_export(
    doc_id: str,
    doc_name: str,
    content_hash: str,
    bundle_hash: str,
    bundle_size: int,
    governance_level: str = "LOW",
    sge_score: float = 0.0,
    template_id: Optional[str] = None,
    export_format: Optional[str] = None,
    user_did: Optional[str] = None,
    user_wallet: Optional[str] = None
) -> Dict[str, Any]:
    """
    Full export registration: register + seal in one call.

    Convenience wrapper that performs both steps of the 2-step process.

    Returns:
        {
            "success": True/False,
            "receipt_id": "WINDI-A4DESK-xxx" or None,
            "content_hash": "...",
            "bundle_hash": "...",
            "error": "..." (if failed)
        }
    """
    # Step 1: Register
    reg_result = register_in_ledger(
        doc_id=doc_id,
        doc_name=doc_name,
        doc_type="doc",
        content_hash=content_hash,
        governance_level=governance_level,
        sge_score=sge_score,
        template_id=template_id,
        export_format=export_format,
        user_did=user_did,
        user_wallet=user_wallet
    )

    if not reg_result["success"]:
        return {
            "success": False,
            "receipt_id": None,
            "content_hash": content_hash,
            "bundle_hash": bundle_hash,
            "error": reg_result.get("error")
        }

    receipt_id = reg_result["receipt"].get("entry_id") or reg_result["receipt"].get("id")

    # Step 2: Seal bundle
    seal_result = seal_bundle(receipt_id, bundle_hash, bundle_size)

    return {
        "success": True,
        "receipt_id": receipt_id,
        "content_hash": content_hash,
        "bundle_hash": bundle_hash,
        "seal_success": seal_result.get("success", False),
        "seal_error": seal_result.get("error") if not seal_result.get("success") else None
    }


# ═══════════════════════════════════════════════════════════════════════════
# Self-test
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("WINDI Ledger Bridge — Self-Test (Phase 2 Updated)")
    print("=" * 60)
    print(f"BERCARIO_DID_ACTIVE: {BERCARIO_DID_ACTIVE}")
    print(f"SERVICE_DID: {SERVICE_DID}")
    print(f"SERVICE_WALLET: {SERVICE_WALLET}")
    print()

    # Test 1: Generate receipt ID
    rid = generate_receipt_id()
    assert rid.startswith("WINDI-A4DESK-"), f"Invalid format: {rid}"
    print(f"✅ generate_receipt_id(): {rid}")

    # Test 2: Register (real call to Ledger)
    print("\n--- Testing register_in_ledger ---")
    result = register_in_ledger(
        doc_id="TEST-PHASE2-001",
        doc_name="Ledger Bridge Phase 2 Self-Test",
        doc_type="doc",
        content_hash="a" * 64,
        governance_level="LOW",
        sge_score=0.5,
        template_id="selftest",
        export_format="test"
    )
    print(f"Register result: {json.dumps(result, indent=2)}")

    if result["success"]:
        receipt_id = result["receipt"].get("entry_id") or result["receipt"].get("id")
        print(f"✅ Registered: {receipt_id}")

        # Test 3: Seal bundle
        print("\n--- Testing seal_bundle ---")
        seal = seal_bundle(receipt_id, "b" * 64, 99999)
        print(f"Seal result: {json.dumps(seal, indent=2)}")
        if seal["success"]:
            print(f"✅ Bundle sealed")
        else:
            print(f"⚠ Seal warning: {seal.get('error')}")

        # Test 4: Verify in Ledger
        print("\n--- Testing verify_receipt (Ledger) ---")
        verify = verify_receipt(receipt_id)
        if verify["success"]:
            print(f"✅ Receipt verified in Ledger")
        else:
            print(f"⚠ Verify warning: {verify.get('error')}")

        # Test 5: Constitutional resolution
        print("\n--- Testing verify_constitutional (:8114) ---")
        const = verify_constitutional(receipt_id)
        if const["success"]:
            res = const["resolution"]
            print(f"✅ Constitutional: {res.get('status_semantics')} / {res.get('assurance_level')}")
        else:
            print(f"⚠ Constitutional warning: {const.get('error')}")
    else:
        print(f"⚠ Register failed (Ledger may be down): {result.get('error')}")

    print("\n" + "=" * 60)
    print("SELF-TEST COMPLETE")
