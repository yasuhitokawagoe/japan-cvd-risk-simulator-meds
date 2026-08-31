import sqlite3

from access_analytics import extract_public_client_ip, prefecture_counts, record_visit


def test_extract_public_client_ip_ignores_private_addresses():
    headers = {"X-Forwarded-For": "10.0.0.2, 8.8.8.8"}
    assert extract_public_client_ip(headers) == "8.8.8.8"


def test_record_visit_does_not_store_ip(tmp_path, monkeypatch):
    database = tmp_path / "visits.sqlite3"
    monkeypatch.setattr(
        "access_analytics.approximate_region",
        lambda _ip: ("JP", "東京都"),
    )

    result = record_visit({"X-Forwarded-For": "8.8.8.8"}, database)

    assert result["total"] == 1
    assert prefecture_counts(database) == [("東京都", 1)]
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(visits)")]
    assert "ip" not in columns
