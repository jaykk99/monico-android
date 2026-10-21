"""Tests for the v4.6 command set: ls/cat/hash/disk/find/date/uptime/sysinfo,
health full, job clear/get, batch execute, /api/version, /api/disk,
DELETE /api/jobs, StatePersistence.clear, and forensics edge cases."""
import hashlib
import json
import os
import re
import tempfile
import unittest
import urllib.error
import urllib.request

from tests.test_smoke import _ensure_server, _get, _get_json, _post, REPO

import app  # noqa: E402  (toga already stubbed by tests.test_smoke)
from factory_core import StatePersistence  # noqa: E402
from forensics import ForensicsScanner  # noqa: E402


def _delete(path, payload=None):
    req = urllib.request.Request(
        "http://127.0.0.1:5056" + path, data=b"",
        method="DELETE", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class NewCommandsTest(unittest.TestCase):
    """Direct run_command tests (no server needed)."""

    def test_help_lists_new_commands(self):
        out = app.run_command("help")
        for cmd in ("ls <path>", "cat <file>", "hash <file>", "disk",
                    "find <dir>", "date", "uptime", "sysinfo", "job clear"):
            self.assertIn(cmd, out)

    def test_health_full_shows_limits(self):
        out = app.run_command("health full")
        self.assertIn("status=", out)
        self.assertIn("limits:", out)
        self.assertIn("disk_free=", out)

    def test_ls_lists_files(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a.txt"), "w").write("x")
        os.mkdir(os.path.join(d, "sub"))
        out = app.run_command("ls " + d)
        self.assertIn("a.txt", out)
        self.assertIn("sub/", out)

    def test_ls_empty_and_bad(self):
        self.assertEqual(app.run_command("ls " + tempfile.mkdtemp()), "(empty)")
        self.assertIn("ERROR", app.run_command("ls /nonexistent-xyz-123"))

    def test_cat_text_file(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "note.txt")
        open(p, "w").write("hello monico")
        self.assertIn("hello monico", app.run_command("cat " + p))

    def test_cat_truncates_long_files(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "big.txt")
        open(p, "w").write("z" * 20000)
        out = app.run_command("cat " + p)
        self.assertIn("truncated at 10000 chars", out)
        self.assertLess(len(out), 12000)

    def test_cat_refuses_binary(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "blob.bin")
        open(p, "wb").write(b"\x00\x01\x02binary")
        self.assertIn("binary", app.run_command("cat " + p))

    def test_cat_usage_and_missing(self):
        self.assertIn("usage", app.run_command("cat"))
        self.assertIn("ERROR", app.run_command("cat /nonexistent-xyz-123/f"))

    def test_hash_matches_sha256(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "h.txt")
        data = b"hash me please"
        open(p, "wb").write(data)
        self.assertEqual(app.run_command("hash " + p),
                         hashlib.sha256(data).hexdigest())

    def test_hash_usage_and_missing(self):
        self.assertIn("usage", app.run_command("hash"))
        self.assertIn("ERROR", app.run_command("hash /nonexistent-xyz-123"))

    def test_disk(self):
        out = app.run_command("disk")
        self.assertIn("total=", out)
        self.assertIn("used=", out)
        self.assertIn("free=", out)

    def test_find_matches_substring(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "report-2026.txt"), "w").write("x")
        open(os.path.join(d, "other.log"), "w").write("x")
        out = app.run_command("find %s report" % d)
        self.assertIn("report-2026.txt", out)
        self.assertNotIn("other.log", out)

    def test_find_no_matches_and_bad_args(self):
        d = tempfile.mkdtemp()
        self.assertEqual(app.run_command("find %s zzz-nope" % d), "no matches")
        self.assertIn("usage", app.run_command("find"))
        self.assertIn("usage", app.run_command("find " + d))
        self.assertIn("ERROR", app.run_command("find /nonexistent-xyz-123 x"))

    def test_date_format(self):
        out = app.run_command("date")
        self.assertRegex(out, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_uptime(self):
        out = app.run_command("uptime")
        self.assertTrue(out.startswith("uptime "))
        self.assertRegex(out, r"\d+s$")

    def test_sysinfo(self):
        out = app.run_command("sysinfo")
        self.assertIn("platform=", out)
        self.assertIn("python=", out)
        self.assertIn("cpus=", out)
        self.assertIn("ram_total=", out)

    def test_job_clear_empties_queue(self):
        app.run_command('job save {"t": "clear-me"}')
        self.assertNotEqual(app.run_command("job list"), "no jobs")
        self.assertEqual(app.run_command("job clear"), "job queue cleared")
        self.assertEqual(app.run_command("job list"), "no jobs")

    def test_job_get(self):
        out = app.run_command('job save {"t": "get-me"}')
        jid = out.split("job saved:")[1].strip()
        got = app.run_command("job get " + jid)
        self.assertIn("get-me", got)
        self.assertIn("ERROR", app.run_command("job get nope"))
        app.run_command("job clear")

    def test_job_save_bad_json(self):
        self.assertIn("ERROR", app.run_command("job save {not json"))

    def test_unknown_goes_to_engine(self):
        out = app.run_command("do something weird")
        self.assertIn("[UNCENSORED]", out)
        self.assertIn("do something weird", out)

    def test_fetch_rejects_non_http(self):
        self.assertIn("ERROR", app.run_command("fetch ftp://example.com/x"))

    def test_empty_command(self):
        self.assertIn("help", app.run_command(""))
        self.assertIn("help", app.run_command("   "))


class BatchApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_server()

    def test_batch_runs_in_order(self):
        code, data = _post("/api/execute/batch",
                           {"commands": ["help", "disk", "bogus-cmd-xyz"]})
        self.assertEqual(code, 200)
        self.assertEqual(len(data["results"]), 3)
        self.assertIn("ls <path>", data["results"][0]["output"])
        self.assertIn("total=", data["results"][1]["output"])
        self.assertIn("[UNCENSORED]", data["results"][2]["output"])

    def test_batch_rejects_non_list(self):
        code, data = _post("/api/execute/batch", {"commands": "help"})
        self.assertEqual(code, 400)
        self.assertIn("error", data)

    def test_batch_handles_non_string_items(self):
        code, data = _post("/api/execute/batch", {"commands": ["disk", 42]})
        self.assertEqual(code, 200)
        self.assertIn("ERROR", data["results"][1]["output"])

    def test_batch_capped_at_20(self):
        code, data = _post("/api/execute/batch",
                           {"commands": ["disk"] * 25})
        self.assertEqual(code, 200)
        self.assertEqual(len(data["results"]), 20)


class MiscApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_server()

    def test_version(self):
        code, data = _get_json("/api/version")
        self.assertEqual(code, 200)
        self.assertEqual(data["version"], "v4.5")
        self.assertIn("ls", data["commands"])
        self.assertIn("sysinfo", data["commands"])

    def test_disk_endpoint(self):
        code, data = _get_json("/api/disk")
        self.assertEqual(code, 200)
        self.assertGreater(data["total_mb"], 0)
        self.assertGreaterEqual(data["free_mb"], 0)
        self.assertGreaterEqual(data["used_mb"], 0)

    def test_jobs_delete_clears_all(self):
        _post("/api/jobs", {"data": {"t": "wipe-me"}})
        code, data = _get_json("/api/jobs")
        self.assertTrue(data["jobs"])
        code, data = _delete("/api/jobs")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        code, data = _get_json("/api/jobs")
        self.assertEqual(data["jobs"], {})


class PersistenceExtraTest(unittest.TestCase):
    def test_clear(self):
        p = os.path.join(tempfile.mkdtemp(), "s.json")
        sp = StatePersistence(p)
        sp.save_job({"a": 1})
        sp.clear()
        self.assertEqual(sp.list_jobs(), {})

    def test_get_missing_returns_none(self):
        p = os.path.join(tempfile.mkdtemp(), "s.json")
        self.assertIsNone(StatePersistence(p).get_job("nope"))

    def test_corrupt_file_loads_empty(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "s.json")
        open(p, "w").write("{not valid json")
        self.assertEqual(StatePersistence(p).load_state(), {})


class ForensicsExtraTest(unittest.TestCase):
    def test_symlinks_skipped(self):
        d = tempfile.mkdtemp()
        real = os.path.join(d, "real.txt")
        open(real, "w").write("data")
        link = os.path.join(d, "link.txt")
        try:
            os.symlink(real, link)
        except OSError:
            self.skipTest("symlinks not supported here")
        records, _ = ForensicsScanner(d).scan_records()
        paths = [r["path"] for r in records]
        self.assertIn("real.txt", paths)
        self.assertNotIn("link.txt", paths)

    def test_deep_scan_empty_dir(self):
        self.assertEqual(ForensicsScanner(tempfile.mkdtemp()).deep_scan(), "")

    def test_scan_records_relative_paths(self):
        d = tempfile.mkdtemp()
        sub = os.path.join(d, "sub")
        os.mkdir(sub)
        open(os.path.join(sub, "x.txt"), "w").write("x")
        records, _ = ForensicsScanner(d).scan_records()
        self.assertEqual(records[0]["path"], os.path.join("sub", "x.txt"))


class MoreCommandsTest(unittest.TestCase):
    def test_head_default_and_n(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "l.txt")
        open(p, "w").write("\n".join("line%d" % i for i in range(50)))
        out = app.run_command("head " + p)
        self.assertEqual(len(out.splitlines()), 20)
        self.assertTrue(out.startswith("line0"))
        out = app.run_command("head %s 3" % p)
        self.assertEqual(out.splitlines(), ["line0", "line1", "line2"])

    def test_head_bad_args(self):
        self.assertIn("usage", app.run_command("head"))
        self.assertIn("ERROR", app.run_command("head /nonexistent-xyz f"))
        d = tempfile.mkdtemp()
        p = os.path.join(d, "l.txt")
        open(p, "w").write("x")
        self.assertIn("ERROR", app.run_command("head %s abc" % p))
        self.assertIn("ERROR", app.run_command("head %s 999" % p))

    def test_head_refuses_binary(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "b.bin")
        open(p, "wb").write(b"\x00\x01")
        self.assertIn("binary", app.run_command("head " + p))

    def test_tail_last_lines(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "l.txt")
        open(p, "w").write("\n".join("line%d" % i for i in range(50)))
        out = app.run_command("tail %s 3" % p)
        self.assertEqual(out.splitlines(), ["line47", "line48", "line49"])
        out = app.run_command("tail " + p)
        self.assertEqual(len(out.splitlines()), 20)
        self.assertTrue(out.endswith("line49"))

    def test_tail_bad_args(self):
        self.assertIn("usage", app.run_command("tail"))
        self.assertIn("ERROR", app.run_command("tail /nonexistent-xyz 5"))

    def test_wc_counts(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "w.txt")
        open(p, "w").write("hello world\nfoo bar baz\n")
        out = app.run_command("wc " + p)
        self.assertIn("2 lines", out)
        self.assertIn("5 words", out)
        self.assertIn("bytes", out)

    def test_wc_bad_args(self):
        self.assertIn("usage", app.run_command("wc"))
        self.assertIn("ERROR", app.run_command("wc /nonexistent-xyz"))

    def test_du(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a.txt"), "w").write("x" * 2048)
        out = app.run_command("du " + d)
        self.assertIn("KB in 1 files", out)
        self.assertIn("ERROR", app.run_command("du /nonexistent-xyz"))

    def test_ps_lists_processes(self):
        out = app.run_command("ps")
        self.assertRegex(out, r"\d+\s+\d")
        self.assertIn("MB", out)

    def test_net(self):
        out = app.run_command("net")
        self.assertIn("sent=", out)
        self.assertIn("recv=", out)

    def test_sysinfo_api(self):
        _ensure_server()
        code, data = _get_json("/api/sysinfo")
        self.assertEqual(code, 200)
        for key in ("platform", "python", "cpus", "ram_total_mb",
                    "uptime_s", "disk"):
            self.assertIn(key, data)
        self.assertIn("total_mb", data["disk"])

    def test_cmdlog_records_api_commands(self):
        _ensure_server()
        app.cmdlog.clear()
        _post("/api/execute", {"command": "disk"})
        _post("/api/execute", {"command": "bogus-cmd"})
        code, data = _get_json("/api/cmdlog")
        self.assertEqual(code, 200)
        cmds = [e["command"] for e in data["commands"]]
        self.assertEqual(cmds[:2], ["bogus-cmd", "disk"])
        self.assertTrue(data["commands"][1]["ok"])
        self.assertTrue(data["commands"][0]["ok"])  # engine replies are not ERRORs

    def test_log_command_shows_recent(self):
        _ensure_server()
        app.cmdlog.clear()
        _post("/api/execute", {"command": "date"})
        out = app.run_command("log")
        self.assertIn("date", out)
        self.assertIn("[OK]", out)


if __name__ == "__main__":
    unittest.main()
