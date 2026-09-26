import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from access_analytics import record_visit, visit_counts, total_visits, prefecture_counts, analytics_db_path


class AccessPersistenceTests(unittest.TestCase):
    def test_seed_once_and_reopen(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "ACCESS_HISTORICAL_ESTIMATE": "500", "IP_GEOLOCATION_ENABLED": "false",
            "RAILWAY_VOLUME_MOUNT_PATH": folder,
        }):
            path = Path(folder) / "access_analytics.sqlite3"
            self.assertEqual(analytics_db_path(), path)
            self.assertEqual(total_visits(), 500)
            self.assertEqual(record_visit({})["total"], 501)
            self.assertEqual(total_visits(), 501)
            self.assertEqual(total_visits(), 501)
            self.assertEqual(record_visit({})["total"], 502)
            with patch.dict(os.environ, {"ACCESS_HISTORICAL_ESTIMATE": "0"}):
                self.assertEqual(total_visits(), 502)  # persists without bootstrap env
            counts = visit_counts()
            self.assertEqual(counts["observed"], 2)
            self.assertEqual(counts["adjustment"], 500)
            self.assertEqual(prefecture_counts(), [("不明", 2)])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM counter_adjustments").fetchone()[0], 1)

    def test_existing_visits_are_not_counted_twice(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "ACCESS_HISTORICAL_ESTIMATE": "0", "IP_GEOLOCATION_ENABLED": "false",
        }):
            path = Path(folder) / "access.sqlite3"
            record_visit({}, path)
            record_visit({}, path)
            with patch.dict(os.environ, {"ACCESS_HISTORICAL_ESTIMATE": "500"}):
                self.assertEqual(total_visits(path), 500)
                self.assertEqual(visit_counts(path)["adjustment"], 498)
                self.assertEqual(record_visit({}, path)["total"], 501)

    def test_parallel_initialization_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "ACCESS_HISTORICAL_ESTIMATE": "500", "IP_GEOLOCATION_ENABLED": "false",
        }):
            path = Path(folder) / "access.sqlite3"
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: record_visit({}, path), range(8)))
            self.assertEqual(total_visits(path), 508)


if __name__ == "__main__":
    unittest.main()
