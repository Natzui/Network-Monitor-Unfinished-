# Network Monitor — Web Dashboard (In development) 

A local-network monitoring dashboard built with Python Flask, HTML/CSS/JavaScript, and Chart.js.

## Features

- Real-time device status
- Ping/ICMP response-time monitoring
- Local device discovery through the OS ARP/neighbor table
- Response-time graph
- Offline and recovery alerts
- Timestamped system logs
- Packet/check counters
- Router and local-PC identification where available
- Device Intelligence page with OS estimates and TTL
- Browser/dashboard notification messages
- Cybersecurity-style dark dashboard
- Automatic refresh every 2 seconds

## Requirements

- Windows 10/11 recommended
- Python 3.10+
- Your computer and target devices must be on the same local network
- Administrator privileges are normally NOT required for the basic version

## Start

### Windows

Double-click `run_windows.bat`.

Or run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Then open:

http://127.0.0.1:5000

## Important discovery limitation

A browser cannot directly ICMP-ping devices. The Flask backend performs the network monitoring.

The basic discovery method reads the operating system's ARP/neighbor table. Therefore, devices that your computer has not learned about may not appear immediately.

For a more aggressive LAN scanner, a future version can add controlled subnet scanning.

## Project structure

```text
NetworkMonitorWeb/
├── app.py
├── requirements.txt
├── run_windows.bat
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## Security note

This is intended for monitoring networks you own or are authorized to administer. Keep the Flask server bound to `127.0.0.1` unless you intentionally configure authentication and network access controls.


## OS detection

The Device Intelligence page estimates an operating system using the TTL value returned by ping. This is a **heuristic**, not a guaranteed OS fingerprint. Firewalls, routers, VPNs, custom network stacks, and changed initial TTL values can make the estimate incorrect.

## Notifications

The dashboard includes an administrator message box. A sent message is recorded in the dashboard alert/log stream and, when browser notifications are permitted, also appears as a desktop browser notification.

It does not send a message to another person's computer or phone.
