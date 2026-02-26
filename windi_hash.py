"""
WINDI Dual-Hash Engine — WS-1 Integration

SHA-256 dual-hash computation for BABEL's export pipeline:
  - content_hash: semantic integrity (canonical document content)
  - bundle_hash: file integrity (exported file bytes)

Principle: "AI processes. Human decides. WINDI guarantees."
Zero-Knowledge: Only hashes leave the system. Never content.

Author: Claude Code (WS-1)
Date: 2026-02-19
"""

import hashlib
import json
from typing import Union


def compute_content_hash(content: Union[str, dict, list]) -> str:
    """
    Compute SHA-256 of canonical document content.

    Args:
        content: Document content as string, dict, or list.
                 If dict/list, serialized with sort_keys=True for determinism.

    Returns:
        Full 64-character hexadecimal SHA-256 hash.

    Examples:
        >>> compute_content_hash("Hello WINDI")
        '7a8b9c...'  # 64 chars

        >>> compute_content_hash({"type": "doc", "blocks": [...]})
        '1234ab...'  # 64 chars, deterministic
    """
    if isinstance(content, (dict, list)):
        # Deterministic serialization: sort keys, no ASCII escaping for Unicode
        canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    else:
        canonical = str(content)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_bundle_hash(filepath: str) -> str:
    """
    Compute SHA-256 of exported file's raw bytes.

    Reads file in 8KB chunks for memory efficiency with large files.

    Args:
        filepath: Path to the exported file (PDF, DOCX, etc.)

    Returns:
        Full 64-character hexadecimal SHA-256 hash.

    Examples:
        >>> compute_bundle_hash("/tmp/export.pdf")
        'abcd12...'  # 64 chars
    """
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════

def compute_dual_hash(content: Union[str, dict, list], filepath: str) -> dict:
    """
    Compute both content_hash and bundle_hash in one call.

    Args:
        content: Document content for semantic hash
        filepath: Path to exported file for bundle hash

    Returns:
        Dict with both hashes: {"content_hash": "...", "bundle_hash": "..."}
    """
    return {
        "content_hash": compute_content_hash(content),
        "bundle_hash": compute_bundle_hash(filepath)
    }


def short_hash(full_hash: str, length: int = 12) -> str:
    """
    Return truncated hash for display purposes.

    Args:
        full_hash: Full 64-char hash
        length: Number of chars to show (default 12)

    Returns:
        Truncated hash with ellipsis: "abc123..."
    """
    if len(full_hash) <= length:
        return full_hash
    return full_hash[:length] + "..."


# ═══════════════════════════════════════════════════════════════════════════
# Self-test
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import tempfile
    import os

    print("WINDI Dual-Hash Engine — Self-Test")
    print("=" * 50)

    # Test 1: content_hash determinism
    h1 = compute_content_hash("Hello WINDI")
    h2 = compute_content_hash("Hello WINDI")
    assert h1 == h2, "FAIL: Not deterministic!"
    assert len(h1) == 64, f"FAIL: Expected 64 chars, got {len(h1)}"
    print(f"✅ content_hash (string): {short_hash(h1)} (deterministic, 64 chars)")

    # Test 2: content_hash with JSON
    h3 = compute_content_hash({
        "type": "doc",
        "content": [{"type": "paragraph", "text": "Test"}]
    })
    assert len(h3) == 64
    print(f"✅ content_hash (JSON):   {short_hash(h3)} (64 chars)")

    # Test 3: JSON key order doesn't matter (sorted internally)
    h4a = compute_content_hash({"b": 2, "a": 1})
    h4b = compute_content_hash({"a": 1, "b": 2})
    assert h4a == h4b, "FAIL: JSON key order should not matter!"
    print(f"✅ content_hash (key order): deterministic")

    # Test 4: bundle_hash
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(b"fake PDF content for testing WINDI")
    tmp.close()
    h5 = compute_bundle_hash(tmp.name)
    assert len(h5) == 64
    assert h5 != h1, "FAIL: bundle_hash should differ from content_hash!"
    print(f"✅ bundle_hash:           {short_hash(h5)} (64 chars, differs)")
    os.unlink(tmp.name)

    # Test 5: compute_dual_hash
    tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp2.write(b"dual hash test file")
    tmp2.close()
    dual = compute_dual_hash("Document content", tmp2.name)
    assert "content_hash" in dual and "bundle_hash" in dual
    assert len(dual["content_hash"]) == 64
    assert len(dual["bundle_hash"]) == 64
    print(f"✅ compute_dual_hash:     both hashes computed")
    os.unlink(tmp2.name)

    print("=" * 50)
    print("ALL TESTS PASSED ✅")
