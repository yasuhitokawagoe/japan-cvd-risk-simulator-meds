import ipaddress
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


UNKNOWN_LOCATION = "不明"


def analytics_db_path() -> Path:
    data_dir = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "/tmp/dm-care-data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "access_analytics.sqlite3"


def extract_public_client_ip(headers) -> str | None:
    if not headers:
        return None
    header_map = {str(key).lower(): str(value) for key, value in headers.items()}
    candidates = []
    for name in ("x-forwarded-for", "x-real-ip"):
        candidates.extend(part.strip() for part in header_map.get(name, "").split(","))
    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.is_global:
            return candidate
    return None


def approximate_region(ip_address: str | None, timeout: float = 1.5) -> tuple[str, str]:
    if os.environ.get("IP_GEOLOCATION_ENABLED", "false").lower() != "true":
        return UNKNOWN_LOCATION, UNKNOWN_LOCATION
    if not ip_address:
        return UNKNOWN_LOCATION, UNKNOWN_LOCATION
    url = f"https://ipwho.is/{ip_address}?lang=ja"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return UNKNOWN_LOCATION, UNKNOWN_LOCATION
    if not payload.get("success", False):
        return UNKNOWN_LOCATION, UNKNOWN_LOCATION
    country_code = str(payload.get("country_code") or UNKNOWN_LOCATION)
    region = str(payload.get("region") or UNKNOWN_LOCATION)
    return country_code, region


def record_visit(headers, db_path: Path | None = None) -> dict:
    path = db_path or analytics_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    client_ip = extract_public_client_ip(headers)
    country_code, region = approximate_region(client_ip)
    visited_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with sqlite3.connect(path, timeout=5) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visited_at TEXT NOT NULL,
                country_code TEXT NOT NULL,
                prefecture TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO visits (visited_at, country_code, prefecture) VALUES (?, ?, ?)",
            (visited_at, country_code, region),
        )
        total = connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        connection.commit()

    return {"total": int(total), "prefecture": region, "country_code": country_code}


def total_visits(db_path: Path | None = None) -> int:
    path = db_path or analytics_db_path()
    if not path.exists():
        return 0
    with sqlite3.connect(path, timeout=5) as connection:
        row = connection.execute("SELECT COUNT(*) FROM visits").fetchone()
    return int(row[0]) if row else 0


def prefecture_counts(db_path: Path | None = None) -> list[tuple[str, int]]:
    path = db_path or analytics_db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path, timeout=5) as connection:
        rows = connection.execute(
            """
            SELECT prefecture, COUNT(*) AS visits
            FROM visits
            GROUP BY prefecture
            ORDER BY visits DESC, prefecture ASC
            """
        ).fetchall()
    return [(str(prefecture), int(visits)) for prefecture, visits in rows]
