import json
import os
import tempfile
import uuid

VALID_STATUSES = ("PENDING", "RUNNING", "DONE", "FAILED")


class StatePersistence:
    """
    Job ID system so factory-run progress survives restarts.
    Writes are atomic (temp file + os.replace) to survive kills mid-write.
    """

    def __init__(self, db_path="monico_factory.json"):
        self.path = db_path

    def load_state(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_state(self, state):
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def save_job(self, data):
        job_id = str(uuid.uuid4())
        state = self.load_state()
        state[job_id] = {"data": data, "status": "PENDING"}
        self._write_state(state)
        return job_id

    def set_status(self, job_id, status):
        """Set a job's status. Returns True if the job existed."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; want one of {VALID_STATUSES}")
        state = self.load_state()
        if job_id not in state:
            return False
        state[job_id]["status"] = status
        self._write_state(state)
        return True

    def get_job(self, job_id):
        return self.load_state().get(job_id)

    def list_jobs(self):
        return self.load_state()


class DataBridge:
    """
    Server-side fetcher to pull logs proactively from a scraper harvester.
    Returns text (truncated) so huge responses can't blow up the UI.
    """

    def fetch_logs(self, endpoint_url, timeout=10, max_chars=20000):
        import requests

        r = requests.get(endpoint_url, timeout=timeout)
        r.raise_for_status()
        text = r.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n…[truncated, {len(text)} chars total]"
        return text
