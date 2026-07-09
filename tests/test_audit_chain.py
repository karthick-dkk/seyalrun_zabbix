"""T9 invariant: the audit hash chain detects any edit or deletion of a
historical row. Pure functions — no DB needed."""

from __future__ import annotations

from libs.audithash import GENESIS, compute_entry_hash, verify_chain


def _build(n: int) -> list[dict]:
    """Build a valid n-row chain."""
    rows = []
    prev = GENESIS
    for seq in range(1, n + 1):
        payload = {"action": f"act{seq}", "user_id": f"u{seq}", "details": {"i": seq}}
        eh = compute_entry_hash(seq, prev, payload)
        rows.append({"seq": seq, "prev_hash": prev, "entry_hash": eh, "payload": payload})
        prev = eh
    return rows


def test_valid_chain_verifies():
    result = verify_chain(_build(5))
    assert result["ok"] is True
    assert result["checked"] == 5


def test_empty_chain_ok():
    assert verify_chain([])["ok"] is True


def test_hash_is_deterministic():
    p = {"action": "login", "user_id": "u1"}
    assert compute_entry_hash(1, GENESIS, p) == compute_entry_hash(1, GENESIS, p)


def test_altered_row_detected():
    rows = _build(4)
    rows[2]["payload"]["action"] = "tampered"  # edit a historical row's content
    result = verify_chain(rows)
    assert result["ok"] is False
    assert result["broken_seq"] == 3
    assert "altered" in result["reason"]


def test_deleted_row_detected():
    rows = _build(4)
    del rows[1]  # remove a middle row -> next row's prev_hash no longer matches
    result = verify_chain(rows)
    assert result["ok"] is False
    assert result["broken_seq"] == 3


def test_reordered_rows_detected():
    rows = _build(3)
    rows[1], rows[2] = rows[2], rows[1]  # swap order
    assert verify_chain(rows)["ok"] is False


def test_first_row_must_chain_to_genesis():
    rows = _build(2)
    rows[0]["prev_hash"] = "f" * 64  # not GENESIS
    result = verify_chain(rows)
    assert result["ok"] is False
    assert result["broken_seq"] == 1
