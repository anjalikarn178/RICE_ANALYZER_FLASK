import subprocess
import platform

def ping_pi(ip: str, timeout_sec: int = 1) -> bool:
    try:
        if platform.system() == "Windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout_sec * 1000), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout_sec), ip]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False