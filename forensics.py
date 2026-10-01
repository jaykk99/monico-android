import os
import hashlib

# Safety bounds so a scan can never hang the on-device server.
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_HASH_BYTES = 1 * 1024 * 1024  # 1 MiB hashed per file
_CHUNK = 64 * 1024


class ForensicsScanner:
    """On-device forensic auditing module for Monico Android.

    Walks a directory tree and records SHA-256 prefixes per file.
    Bounded by max_files / max_hash_bytes so it cannot hang the server.
    """

    def __init__(self, target_path="."):
        self.target = target_path

    def _iter_files(self, max_files):
        """Yield up to max_files regular files under target (skips symlinks)."""
        seen = 0
        for root, _dirs, files in os.walk(self.target, followlinks=False):
            for name in files:
                if seen >= max_files:
                    return
                fp = os.path.join(root, name)
                try:
                    if not os.path.isfile(fp) or os.path.islink(fp):
                        continue
                except OSError:
                    continue
                seen += 1
                yield fp

    def _hash_file(self, fp, max_bytes):
        """SHA-256 over at most max_bytes, read in chunks. Returns (hex, size)."""
        h = hashlib.sha256()
        size = 0
        remaining = max_bytes
        with open(fp, "rb") as fh:  # handle closed by context manager
            while remaining > 0:
                chunk = fh.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
                remaining -= len(chunk)
        try:
            size = os.path.getsize(fp)
        except OSError:
            pass
        return h.hexdigest(), size

    def scan_records(self, max_files=DEFAULT_MAX_FILES,
                     max_bytes=DEFAULT_MAX_HASH_BYTES):
        """Return a list of {path, size, sha8} dicts. Raises on bad target."""
        target = os.path.abspath(os.path.expanduser(self.target))
        if not os.path.isdir(target):
            raise ValueError(f"scan target is not a directory: {self.target}")
        records = []
        for fp in self._iter_files(max_files):
            try:
                digest, size = self._hash_file(fp, max_bytes)
            except (OSError, PermissionError):
                continue
            records.append({
                "path": os.path.relpath(fp, target) or fp,
                "size": size,
                "sha8": digest[:8],
            })
        truncated = len(records) >= max_files
        return records, truncated

    def deep_scan(self, max_files=100):
        """Legacy text summary (kept for compatibility)."""
        records, _ = self.scan_records(max_files=max_files)
        return "\n".join(f"{r['path']} | {r['sha8']}" for r in records)
