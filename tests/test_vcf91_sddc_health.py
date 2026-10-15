"""Offline checks for VCF 9.1.x health reports. Author: Paul Bryant."""

import argparse
import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from vcf9 import sddc_health as health


class FakeClient:
    def __init__(self, version="9.1.1.0"):
        self.version = version
        self.calls = []

    def request_json(self, method, path):
        self.calls.append((method, path))
        return {"role": "SddcManager", "version": self.version}

    def get_pages(self, path, *, filters=None):
        self.calls.append((path, filters))
        if path == "/v1/domains":
            return [{"id": "domain-1", "name": "Management"}]
        if path.endswith("/resource-certificates"):
            return [
                {"resourceName": "=sensitive", "isInstalled": True, "numberOfDaysToExpire": 20,
                 "expirationStatus": "ACTIVE", "pemEncoded": "private material must not be exported"},
                {"resourceName": "old candidate", "isInstalled": False, "numberOfDaysToExpire": -1,
                 "expirationStatus": "EXPIRED"},
            ]
        if path == "/v1/tasks":
            return [
                {"id": "1", "name": "Upgrade", "status": "Failed", "secret": "do not export"},
                {"id": "2", "name": "Inventory", "status": "Successful"},
            ]
        raise AssertionError(path)


class SddcHealthTests(unittest.TestCase):
    def test_selects_installed_expiring_certificates_and_failed_tasks(self):
        client = FakeClient()
        now = datetime(2026, 10, 15, tzinfo=timezone.utc)
        report = health.collect_health(client, days=30, expires_within=60, now=now)
        self.assertTrue(report["certificates"][0]["attention"])
        self.assertFalse(report["certificates"][1]["attention"])
        self.assertEqual([task["id"] for task in report["failed_tasks"]], ["1"])
        task_call = client.calls[-1]
        self.assertEqual(task_call[0], "/v1/tasks")
        self.assertEqual(task_call[1]["completedAfter"], report["completed_after"])

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            output = Path(directory)
            health.export_health(report, output)
            with (output / "certificate_attention.csv").open(encoding="utf-8-sig", newline="") as stream:
                certificate_rows = list(csv.DictReader(stream))
            self.assertEqual(len(certificate_rows), 1)
            self.assertEqual(certificate_rows[0]["resourceName"], "'=sensitive")
            self.assertNotIn("pemEncoded", certificate_rows[0])
            with (output / "certificates.csv").open(encoding="utf-8-sig", newline="") as stream:
                all_certificate_rows = list(csv.DictReader(stream))
            self.assertEqual(all_certificate_rows[1]["numberOfDaysToExpire"], "-1")
            with (output / "failed_tasks.csv").open(encoding="utf-8-sig", newline="") as stream:
                task_rows = list(csv.DictReader(stream))
            self.assertNotIn("secret", task_rows[0])

    def test_rejects_other_versions_before_retrieving_inventory(self):
        client = FakeClient(version="9.0.2.0")
        with self.assertRaisesRegex(RuntimeError, "Expected SDDC Manager 9.1.x"):
            health.collect_health(client, days=30, expires_within=60)
        self.assertEqual(len(client.calls), 1)

    def test_day_arguments_have_bounds(self):
        self.assertEqual(health.bounded_days("30"), 30)
        for value in ("0", "3651", "abc"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                health.bounded_days(value)


if __name__ == "__main__":
    unittest.main()
