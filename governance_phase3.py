# ============================================================
# PHASE 3: GOVERNANCE EXPORT MODULE
# File: /opt/windi/a4desk-editor/governance_phase3.py
# Version: 1.0.0
# ============================================================
"""
WINDI Governance Export Functions

This module provides document governance metadata extraction,
structure validation, and audit trail functionality for 
A4 Desk BABEL v4.7-gov.

Functions:
- extract_block_governance: Calculate human/AI authorship percentages
- validate_structure: Check document against template rules
- extract_blocks_from_html: Parse blocks from HTML content
- build_governance_ledger_html: Generate PDF governance section
- save_governance_audit: Store audit trail (metadata only)
"""

import re
import json
from datetime import datetime


def extract_block_governance(blocks):
    """
    Extract governance metadata from document blocks.
    
    Args:
        blocks: List of block dicts with blockType and blockOrigin
        
    Returns:
        Dict with total_blocks, human_blocks, ai_blocks, human_authored_percentage
    """
    if not blocks:
        return {
            "total_blocks": 0, 
            "human_blocks": 0, 
            "ai_blocks": 0, 
            "human_authored_percentage": 100.0
        }
    
    total = len(blocks)
    human = sum(1 for b in blocks if b.get("blockOrigin") == "human")
    ai = sum(1 for b in blocks if b.get("blockOrigin") == "ai-assisted")
    
    # Blocks without explicit origin are considered human-authored
    untagged = total - human - ai
    human += untagged
    
    human_pct = round((human / total) * 100, 1) if total else 100.0
    
    return {
        "total_blocks": total, 
        "human_blocks": human, 
        "ai_blocks": ai, 
        "human_authored_percentage": human_pct
    }


def validate_structure(blocks, template_id):
    """
    Validate document structure against template rules.
    
    Args:
        blocks: List of block dicts
        template_id: Template identifier string
        
    Returns:
        Dict with structure_valid, missing_required_blocks, template_id
    """
    TEMPLATE_RULES = {
        "german_gov_v1": [
            {"id": "empfaenger", "required": True}, 
            {"id": "betreff", "required": True}, 
            {"id": "body", "required": True}
        ],
        "business_letter": [
            {"id": "recipient", "required": True}, 
            {"id": "subject", "required": True}, 
            {"id": "body", "required": True}
        ],
        "internal_memo": [
            {"id": "header", "required": True}, 
            {"id": "body", "required": True}
        ],
        "academic_paper": [
            {"id": "title", "required": True},
            {"id": "abstract", "required": True},
            {"id": "body", "required": True}
        ]
    }
    
    rules = TEMPLATE_RULES.get(template_id, [])
    
    if not rules:
        return {
            "structure_valid": True, 
            "missing_required_blocks": [], 
            "template_id": template_id or "unknown"
        }
    
    block_types = [b.get("blockType") for b in blocks] if blocks else []
    
    missing_required = [
        rule["id"] for rule in rules 
        if rule.get("required") and rule["id"] not in block_types
    ]
    
    return {
        "structure_valid": len(missing_required) == 0, 
        "missing_required_blocks": missing_required, 
        "template_id": template_id
    }


def extract_blocks_from_html(html_content):
    """
    Fallback: Extract block structure from HTML content.
    Parses institutional block divs from editor output.
    
    Args:
        html_content: HTML string from document editor
        
    Returns:
        List of block dicts with blockType and blockOrigin
    """
    blocks = []
    
    # Pattern for institutional blocks with data attributes
    pattern = r'<div[^>]*class="[^"]*inst-block[^"]*"[^>]*data-block-type="([^"]+)"[^>]*(?:data-block-origin="([^"]*)")?'
    matches = re.findall(pattern, html_content, re.IGNORECASE)
    
    for match in matches:
        block_type = match[0] if len(match) > 0 else "unknown"
        origin = match[1] if len(match) > 1 and match[1] else "human"
        blocks.append({
            "blockType": block_type, 
            "blockOrigin": origin
        })
    
    # If no institutional blocks found, treat as single human-authored body
    if not blocks:
        blocks.append({
            "blockType": "body", 
            "blockOrigin": "human"
        })
    
    return blocks


def build_governance_ledger_html(governance_stats, structure_check, template_id):
    """Build COMPACT Governance Ledger for PDF export."""
    structure_status = "VALID" if structure_check["structure_valid"] else "WARNING"
    # v4.8: COMPACT single line
    return f"""
    <div style="font-size:7pt;color:#999;margin-top:8pt;padding:3pt 0;border-top:0.5pt solid #ddd;text-align:center;">
        Governed via WINDI • Human: {governance_stats['human_authored_percentage']}% • Template: {template_id} • Structure: {structure_status}
    </div>
    """

def save_governance_audit(db_func, doc_id, governance_stats, structure_check, receipt_id, institutional_profile=None):
    """
    Save governance audit entry to database.
    Stores only metadata, never document content.
    Args:
        db_func: Function to get database connection (get_db)
        doc_id: Document identifier
        governance_stats: Dict from extract_block_governance
        structure_check: Dict from validate_structure
        receipt_id: WINDI receipt identifier
        institutional_profile: Optional ISP dict from Phase 4
    Returns:
        True on success, False on error
    """
    try:
        conn = db_func()
        cursor = conn.cursor()
        # Create audit table if not exists (with ISP fields)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS governance_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                receipt_id TEXT,
                timestamp TEXT NOT NULL,
                human_authored_percentage REAL,
                ai_assisted_blocks INTEGER,
                total_blocks INTEGER,
                structure_valid INTEGER,
                template_id TEXT,
                missing_blocks TEXT,
                institutional_profile_id TEXT,
                institutional_profile_type TEXT
            )
        ''')
        # Add ISP columns if missing (for existing databases)
        try:
            cursor.execute('ALTER TABLE governance_audit ADD COLUMN institutional_profile_id TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE governance_audit ADD COLUMN institutional_profile_type TEXT')
        except:
            pass
        # Extract ISP data
        isp_id = None
        isp_type = None
        if institutional_profile:
            isp_id = institutional_profile.get("profile_id")
            isp_type = institutional_profile.get("profile_type")
        # Insert audit record
        cursor.execute('''
            INSERT INTO governance_audit
            (document_id, receipt_id, timestamp, human_authored_percentage,
             ai_assisted_blocks, total_blocks, structure_valid, template_id, missing_blocks,
             institutional_profile_id, institutional_profile_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc_id,
            receipt_id,
            datetime.utcnow().isoformat(),
            governance_stats["human_authored_percentage"],
            governance_stats["ai_blocks"],
            governance_stats["total_blocks"],
            1 if structure_check["structure_valid"] else 0,
            structure_check["template_id"],
            json.dumps(structure_check["missing_required_blocks"]),
            isp_id,
            isp_type
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[GOVERNANCE] Audit save error: {e}")
        return False


# ============================================================
# Module info
# ============================================================
__version__ = "1.0.0"
__author__ = "WINDI Publishing House"
__description__ = "Phase 3 Governance Export Functions"


