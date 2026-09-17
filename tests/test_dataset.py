"""Tests for the GASTAT dataset loader."""

from backend.data.dataset import DatasetService


def _fresh_service():
    # A fresh instance (bypasses the module cache) for independent assertions.
    return DatasetService()


def test_loads_records():
    svc = _fresh_service()
    assert svc.is_available()
    assert svc.records
    assert len(svc.records) > 50


def test_sectors_are_exposed():
    svc = _fresh_service()
    sectors = svc.sectors()
    assert "Healthcare" in sectors
    assert "Education" in sectors
    assert "Transportation & Logistics" in sectors


def test_required_columns_are_present():
    svc = _fresh_service()
    record = svc.records[0]
    for field in (
        "sector",
        "indicator",
        "verified_value",
        "unit",
        "year",
        "data_status",
        "simulation_ready",
        "source",
    ):
        assert field in record


def test_missing_rows_are_not_verified():
    svc = _fresh_service()
    # Rows flagged "Missing" must not be "verified".
    missing = [r for r in svc.records if r["data_status"] == "Missing"]
    assert missing
    assert all(not r["verified"] for r in missing)


def test_duplicate_environment_rows_are_deduplicated():
    svc = _fresh_service()
    # The Environment sector contains duplicate Basic sanitation rows in the
    # raw file; the loader keeps the best one per (sector, indicator, year).
    homes = [
        r
        for r in svc.records
        if r["sector"] == "Environment" and "sanitation" in r["indicator"].lower()
    ]
    assert len(homes) <= 2


def test_simulation_ready_filter():
    svc = _fresh_service()
    ready = [r for r in svc.records if r["simulation_ready"] and r["verified"]]
    assert ready
    assert all(r["verified"] for r in ready)


def test_summary_counts_and_percent_mean():
    svc = _fresh_service()
    summary = svc.summary_for("Healthcare")
    assert summary["verifiedIndicatorCount"] >= 5
    assert summary["indicatorCount"] == summary["verifiedIndicatorCount"] + \
        summary["missingIndicatorCount"]
    # Percent-unit verified values average is bounded 0-100.
    if summary["meanPercentValue"] is not None:
        assert 0 <= summary["meanPercentValue"] <= 100


def test_global_report_shape():
    svc = _fresh_service()
    report = svc.global_report()
    assert report["loaded"] is True
    assert report["sectorCount"] >= 15
    assert report["totalRows"] > 0
    assert report["sources"]  # GASTAT sources present


def test_missing_dataset_file_is_graceful():
    svc = DatasetService(path="C:/definitely/not/a/real/path.csv")
    assert svc.is_available() is False
    assert svc.error is not None
    assert svc.records == []