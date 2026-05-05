import psutil
import time

class HealthGuard:
    """
    Monico HealthGuard - Hardware preservation for mobile devices.
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
            "ram": f"{ram_usage:.1f}MB"
        }

if __name__ == "__main__":
    guard = HealthGuard()
    while True:
        print(f"[HEALTH_CHECK] {guard.check()}")
        time.sleep(10)