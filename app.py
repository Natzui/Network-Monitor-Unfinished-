from flask import Flask, render_template, jsonify, request
import subprocess
import platform
import re
import socket
import threading
import time
from collections import deque
from datetime import datetime

app = Flask(__name__)

state = {
    "devices": {},
    "logs": deque(maxlen=300),
    "alerts": deque(maxlen=50),
    "history": deque(maxlen=60),
    "running": True,
    "last_discovery": None,
}
lock = threading.Lock()

def log(message, level="INFO"):
    item = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "level": level
    }
    with lock:
        state["logs"].appendleft(item)

def alert(message, level="warning"):
    item = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "level": level
    }
    with lock:
        state["alerts"].appendleft(item)
    log(message, "ALERT")

def local_network():
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except OSError:
        local_ip = "127.0.0.1"

    # Best-effort gateway detection from Windows route table.
    gateway = "Unknown"
    if platform.system().lower() == "windows":
        try:
            out = subprocess.check_output(
                ["cmd", "/c", "route", "print", "0.0.0.0"],
                text=True, errors="ignore"
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "0.0.0.0":
                    gateway = parts[2]
                    break
        except Exception:
            pass

    return hostname, local_ip, gateway

def discover_arp():
    devices = {}
    system = platform.system().lower()

    try:
        if system == "windows":
            output = subprocess.check_output(
                ["arp", "-a"], text=True, errors="ignore"
            )
            for line in output.splitlines():
                m = re.search(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+\w+", line)
                if m:
                    ip, mac = m.group(1), m.group(2).upper()
                    devices[ip] = {"ip": ip, "mac": mac}
        else:
            output = subprocess.check_output(
                ["ip", "neigh"], text=True, errors="ignore"
            )
            for line in output.splitlines():
                m = re.search(r"^(\d+\.\d+\.\d+\.\d+).*lladdr\s+([0-9a-fA-F:]{17})\s+(\w+)", line)
                if m:
                    devices[m.group(1)] = {"ip": m.group(1), "mac": m.group(2).upper(), "state": m.group(3)}
    except Exception as exc:
        log(f"Discovery error: {exc}", "ERROR")

    return devices

def ping(ip):
    system = platform.system().lower()
    command = ["ping", "-n", "1", "-w", "1000", ip] if system == "windows" else ["ping", "-c", "1", "-W", "1", ip]

    started = time.perf_counter()
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True, errors="ignore")
        elapsed = round((time.perf_counter() - started) * 1000, 1)

        match = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", output, re.I)
        latency = round(float(match.group(1)), 1) if match else elapsed

        # TTL is only a heuristic. It is not a reliable OS fingerprint.
        ttl_match = re.search(r"TTL[=\s](\d+)", output, re.I)
        ttl = int(ttl_match.group(1)) if ttl_match else None
        if ttl is None:
            ttl_match = re.search(r"ttl[=\s](\d+)", output, re.I)
            ttl = int(ttl_match.group(1)) if ttl_match else None

        if ttl is not None:
            if ttl <= 64:
                os_guess = "Linux / Unix (heuristic)"
            elif ttl <= 128:
                os_guess = "Windows (heuristic)"
            else:
                os_guess = "Network device / other (heuristic)"
        else:
            os_guess = "Unknown"

        return True, latency, ttl, os_guess
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, None, None, "Unknown"
    except Exception:
        return False, None, None, "Unknown"

def system_name():
    return platform.system()

def monitor_loop():
    hostname, local_ip, gateway = local_network()
    log(f"Monitor started on {hostname} ({local_ip})")
    if gateway != "Unknown":
        log(f"Default gateway detected: {gateway}")

    while state["running"]:
        found = discover_arp()
        now = datetime.now().strftime("%H:%M:%S")

        # Always monitor local host and gateway when available.
        if local_ip not in found:
            found[local_ip] = {"ip": local_ip, "mac": "LOCAL"}
        if gateway != "Unknown" and gateway not in found:
            found[gateway] = {"ip": gateway, "mac": "GATEWAY"}

        with lock:
            previous = {ip: dict(v) for ip, v in state["devices"].items()}

        # Ping all discovered devices. This is intentionally conservative:
        # it monitors devices already visible through the local ARP/neighbor table.
        for ip, meta in found.items():
            ok, latency, ttl, os_guess = ping(ip)
            old = previous.get(ip)
            status = "ONLINE" if ok else "OFFLINE"

            item = {
                "ip": ip,
                "mac": meta.get("mac", "—"),
                "status": status,
                "latency": latency,
                "last_seen": now,
                "history": (old or {}).get("history", [])[-29:] + ([latency] if latency is not None else []),
                "checks": (old or {}).get("checks", 0) + 1,
                "packets": (old or {}).get("packets", 0) + 1,
                "type": "Router" if ip == gateway else ("This PC" if ip == local_ip else "Network device"),
                "ttl": ttl,
                "os": "Windows" if ip == local_ip and system_name() == "Windows" else os_guess,
            }

            if old:
                if old.get("status") == "ONLINE" and status == "OFFLINE":
                    alert(f"{ip} stopped responding", "danger")
                elif old.get("status") == "OFFLINE" and status == "ONLINE":
                    alert(f"{ip} is back online", "success")

            with lock:
                state["devices"][ip] = item

        with lock:
            online = sum(1 for d in state["devices"].values() if d["status"] == "ONLINE")
            offline = sum(1 for d in state["devices"].values() if d["status"] == "OFFLINE")
            latencies = [d["latency"] for d in state["devices"].values() if d["latency"] is not None]
            avg = round(sum(latencies) / len(latencies), 1) if latencies else 0
            state["history"].append({
                "time": now,
                "latency": avg,
                "online": online,
                "offline": offline
            })
            state["last_discovery"] = now

        time.sleep(3)

threading.Thread(target=monitor_loop, daemon=True).start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    with lock:
        devices = list(state["devices"].values())
        online = sum(d["status"] == "ONLINE" for d in devices)
        offline = sum(d["status"] == "OFFLINE" for d in devices)
        latencies = [d["latency"] for d in devices if d["latency"] is not None]
        avg = round(sum(latencies) / len(latencies), 1) if latencies else 0
        packets = sum(d["packets"] for d in devices)
        return jsonify({
            "devices": devices,
            "online": online,
            "offline": offline,
            "total": len(devices),
            "latency": avg,
            "packets": packets,
            "history": list(state["history"]),
            "alerts": list(state["alerts"]),
            "logs": list(state["logs"]),
            "last_discovery": state["last_discovery"]
        })

@app.post("/api/discover")
def discover():
    # The background monitor performs discovery automatically.
    log("Manual device discovery requested")
    return jsonify({"ok": True})

@app.post("/api/notify")
def notify():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"ok": False, "error": "Message is required"}), 400
    alert(f"ADMIN MESSAGE: {message}", "info")
    return jsonify({"ok": True})

@app.post("/api/clear-logs")
def clear_logs():
    with lock:
        state["logs"].clear()
        state["alerts"].clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
