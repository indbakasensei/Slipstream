"""Encoding regression test — Fluent 26.1 on Windows emits UTF-16 LE
transcripts with a BOM. This exercises the encoding sniffer in the tap."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.telemetry import TelemetryTap


def test_tap_reads_utf16_le_transcript(tmp_path):
    hist = tmp_path / "history.out"
    trn = tmp_path / "transcript.trn"

    hist.write_text(
        '"cfdauto_history"\n'
        '"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
        "1 0.10 0.010\n2 0.15 0.011\n"
    )
    residual_text = (
        "  iter  continuity  x-velocity  y-velocity  z-velocity  k  omega\n"
        "     1   1.0e-2      2.0e-3      2.0e-3      1.5e-3      3e-3  4e-3\n"
        "     2   5.0e-3      1.5e-3      1.5e-3      1.0e-3      2e-3  3e-3\n"
    )
    # Write UTF-16 LE with BOM — mimicking Fluent 26.1
    trn.write_bytes(b"\xff\xfe" + residual_text.encode("utf-16-le"))

    events: List[dict] = []
    tap = TelemetryTap(hist, trn, lambda t, **d: events.append(d),
                       max_it=100, poll_hz=1000)
    tap._poll_once()

    assert len(events) == 2
    r1 = events[0].get("residuals")
    assert r1 is not None, "residuals missing — encoding sniff failed"
    assert r1["continuity"] == 1.0e-2
    assert r1["omega"] == 4.0e-3


def test_tap_reads_utf16_le_without_bom(tmp_path):
    """Some Fluent releases skip the BOM after the first flush — the
    heuristic (many 0x00 bytes at odd positions) must still trigger."""
    hist = tmp_path / "history.out"
    trn = tmp_path / "transcript.trn"

    hist.write_text(
        '"cfdauto_history"\n'
        '"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
        "1 0.10 0.010\n"
    )
    text = ("  iter  continuity  x-velocity  y-velocity  z-velocity  k  omega\n"
            "     1   1.0e-2      2.0e-3      2.0e-3      1.5e-3      3e-3  4e-3\n")
    trn.write_bytes(text.encode("utf-16-le"))            # no BOM

    events: List[dict] = []
    tap = TelemetryTap(hist, trn, lambda t, **d: events.append(d),
                       max_it=100, poll_hz=1000)
    tap._poll_once()

    assert len(events) == 1
    assert events[0].get("residuals") is not None
    assert events[0]["residuals"]["continuity"] == 1.0e-2


def test_tap_still_reads_utf8(tmp_path):
    """Regression: don't break Fluent versions that emit plain UTF-8."""
    hist = tmp_path / "history.out"
    trn = tmp_path / "transcript.trn"
    hist.write_text(
        '"cfdauto_history"\n'
        '"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
        "1 0.10 0.010\n"
    )
    trn.write_text(
        "  iter  continuity  x-velocity  y-velocity  z-velocity  k  omega\n"
        "     1   1.0e-2      2.0e-3      2.0e-3      1.5e-3      3e-3  4e-3\n"
    )
    events: List[dict] = []
    tap = TelemetryTap(hist, trn, lambda t, **d: events.append(d),
                       max_it=100, poll_hz=1000)
    tap._poll_once()
    assert events[0].get("residuals")["continuity"] == 1.0e-2
