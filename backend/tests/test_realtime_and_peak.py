"""Realtime notification + peak simulation smoke tests (no Redis/DB required)."""

from __future__ import annotations

from app.realtime.notifications import notify
from scripts.peak_arrival_sim import report, run_sim


def test_notify_logs_without_redis():
    result = notify(
        kind="match",
        title="Driver matched",
        body="Test driver · ABC123 · ETA soon",
        audience=[],
        data={"trip_id": "x"},
    )
    assert result["kind"] == "match"
    assert result["logged"] is True


def test_peak_arrival_sim_gates():
    metrics = run_sim(n_drivers=60, n_guests=150, window_min=20)
    summary = report(metrics, n_guests=150)
    assert summary["capacity_violations"] == 0
    assert summary["match_one_latency_ms"]["p95_ok"]
    assert summary["starved_guests"] / 150 <= 0.15
    assert summary["matched_assignments"] > 0
