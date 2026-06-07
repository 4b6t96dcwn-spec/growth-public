#!/usr/bin/env python3
"""Advertise growth API via Bonjour (_growth._tcp) for iPhone auto-discovery."""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import get_server_ports, local_ip

try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:
    print("Install: pip install zeroconf")
    sys.exit(1)


def main():
    _, api_port = get_server_ports()
    ip = local_ip()
    hostname = socket.gethostname().split(".")[0]

    info = ServiceInfo(
        "_growth._tcp.local.",
        f"growth-{hostname}._growth._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=api_port,
        properties={"path": "/api/v1", "https": "true"},
        server=f"{hostname}.local.",
    )

    zc = Zeroconf()
    zc.register_service(info)
    print(f"✅ Bonjour: growth on {ip}:{api_port} as growth-{hostname}._growth._tcp")
    print("   Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    main()