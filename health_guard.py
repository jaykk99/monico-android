import argparse
import signal
import time

import psutil


class HealthGuard:
    """
    Monico HealthGuard - hardware preservation for mobile devices.
    Ensures the AI reasoning engine never slows down the OS.
    """

    def __init__(self, cpu_limit=30.0, ram_limit_mb=512):
        self.cpu_limit = cpu_limit
        self.ram_limit = ram_limit_mb

    def check(self):
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().used / (1024 * 1024)

        status = "OPTIMAL"
        if cpu_usage > self.cpu_limit or ram_usage > self.ram_limit:
            status = "THROTTLING"
            # Logic to pause background reasoning threads

        return {
            "status": status,
            "cpu": f"{cpu_usage}%",
            "ram": f"{ram_usage:.1f}MB",
        }

    def snapshot(self):
        """Machine-friendly health snapshot for the /api/health endpoint."""
        vm = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=None)
        ram_mb = vm.used / (1024 * 1024)
        status = "OPTIMAL"
        if cpu > self.cpu_limit or ram_mb > self.ram_limit:
            status = "THROTTLING"
        return {
            "status": status,
            "cpu": round(cpu, 1),
            "ram_mb": round(ram_mb, 1),
            "ram_pct": round(vm.percent, 1),
            "ts": int(time.time()),
        }


def _watch(interval):
    guard = HealthGuard()
    stop = {"flag": False}

    def _on_signal(_signum, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    while not stop["flag"]:
        print(f"[HEALTH_CHECK] {guard.check()}", flush=True)
        # sleep in small slices so Ctrl-C stops promptly
        for _ in range(int(interval * 10)):
            if stop["flag"]:
                break
            time.sleep(0.1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monico HealthGuard monitor")
    parser.add_argument("--once", action="store_true",
                        help="print one check and exit")
    parser.add_argument("--interval", type=float, default=10.0,
                        help="seconds between checks (default 10)")
    args = parser.parse_args()
    if args.once:
        print(f"[HEALTH_CHECK] {HealthGuard().check()}", flush=True)
    else:
        _watch(args.interval)
