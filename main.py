#!/usr/bin/env python3
"""
growth — independent application entry point.

Usage:
    python3 main.py install
    python3 main.py start [--ui-port 21322] [--api-port 21322] [--save-ports]
    python3 main.py serve --port 21322
    python3 main.py api --port 21322

Ports resolve in order: CLI args → GROWTH_UI_PORT / GROWTH_API_PORT env → config.json
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
VENV_STREAMLIT = ROOT / ".venv" / "bin" / "streamlit"
VENV_UVICORN = ROOT / ".venv" / "bin" / "uvicorn"

from utils import DEFAULT_PORT, get_server_ports

DEFAULT_UI_PORT = DEFAULT_PORT
DEFAULT_API_PORT = DEFAULT_PORT
CERT_DIR = ROOT / "certs"
CERT_FILE = CERT_DIR / "cert.pem"
KEY_FILE = CERT_DIR / "key.pem"


def _python() -> str:
    return str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def _save_ports(ui_port: int, api_port: int) -> None:
    cfg = _load_config()
    cfg["ui_port"] = ui_port
    cfg["api_port"] = api_port
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"✅ Saved ports to {CONFIG_PATH}: ui={ui_port}, api={api_port}")


def resolve_ports(ui_port: int | None = None, api_port: int | None = None) -> tuple[int, int]:
    cfg = _load_config()
    ui = (
        ui_port
        or _env_int("GROWTH_UI_PORT")
        or int(cfg.get("ui_port", DEFAULT_UI_PORT))
    )
    api = (
        api_port
        or _env_int("GROWTH_API_PORT")
        or int(cfg.get("api_port", DEFAULT_API_PORT))
    )
    return ui, api


def _env_int(name: str) -> int | None:
    val = os.environ.get(name)
    if val and val.isdigit():
        return int(val)
    return None


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _check_port(port: int, label: str) -> None:
    if not port_available(port):
        print(f"❌ {label} port {port} is already in use. Pick another:")
        print(f"   ./run.sh --ui-port <port> --api-port <port>")
        print(f"   GROWTH_UI_PORT=<port> ./run.sh")
        sys.exit(1)


def _ensure_certs() -> None:
    if CERT_FILE.exists() and KEY_FILE.exists():
        return
    script = ROOT / "scripts" / "generate_cert.sh"
    if not script.exists():
        print("❌ Missing certs/ and generate_cert.sh. Run: bash scripts/generate_cert.sh")
        sys.exit(1)
    subprocess.check_call(["bash", str(script)])


def _scheme(use_https: bool) -> str:
    return "https" if use_https else "http"


def _streamlit_cmd(ui_port: int, use_https: bool) -> list[str]:
    streamlit = str(VENV_STREAMLIT if VENV_STREAMLIT.exists() else "streamlit")
    cmd = [
        streamlit, "run", str(ROOT / "app.py"),
        "--server.address", "0.0.0.0",
        "--server.port", str(ui_port),
        "--browser.gatherUsageStats", "false",
    ]
    if use_https:
        cmd += ["--server.sslCertFile", str(CERT_FILE), "--server.sslKeyFile", str(KEY_FILE)]
    return cmd


def _uvicorn_cmd(api_port: int, use_https: bool) -> list[str]:
    uvicorn = str(VENV_UVICORN if VENV_UVICORN.exists() else "uvicorn")
    cmd = [uvicorn, "api:app", "--host", "0.0.0.0", "--port", str(api_port)]
    if use_https:
        cmd += ["--ssl-certfile", str(CERT_FILE), "--ssl-keyfile", str(KEY_FILE)]
    return cmd


def _print_access(ui_port: int, api_port: int, use_https: bool = False) -> None:
    ip = local_ip()
    scheme = _scheme(use_https)
    print()
    print("🌱 growth running")
    print(f"   Mac UI:     {scheme}://localhost:{ui_port}")
    print(f"   iPhone UI:  {scheme}://{ip}:{ui_port}")
    print(f"   API:        {scheme}://{ip}:{api_port}/api/v1/health")
    print()
    if not use_https:
        print("   ⚠️  iPhone Safari HTTPS-Only blocks plain http://")
        print("      Fix A: ./run.sh --https   (recommended)")
        print("      Fix B: Settings → Apps → Safari → Advanced → turn off HTTPS-Only")
        print(f"      Fix C: type full URL including port: http://{ip}:{ui_port}")
    else:
        print("   On iPhone: tap 'Show Details' → 'visit this website' for self-signed cert")
    print("   Same Wi-Fi required. Firewall may need to allow Python.")
    print("   Ctrl+C to stop")
    print()


def cmd_install(_args):
    if not VENV_PYTHON.parent.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(ROOT / ".venv")])
    subprocess.check_call([_python(), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    print(f"✅ Installed into {ROOT / '.venv'}")


def cmd_serve(args):
    ui_port, _ = resolve_ports(ui_port=args.port)
    _check_port(ui_port, "UI")
    if args.save_ports:
        _, api_port = resolve_ports()
        _save_ports(ui_port, api_port)
    if args.https:
        _ensure_certs()

    _print_access(ui_port, resolve_ports()[1], use_https=args.https)
    subprocess.check_call(_streamlit_cmd(ui_port, args.https))


def cmd_api(args):
    _, api_port = resolve_ports(api_port=args.port)
    _check_port(api_port, "API")
    if args.save_ports:
        ui_port, _ = resolve_ports()
        _save_ports(ui_port, api_port)
    if args.https:
        _ensure_certs()

    _print_access(resolve_ports()[0], api_port, use_https=args.https)
    subprocess.check_call(_uvicorn_cmd(api_port, args.https))


def cmd_start(args):
    ui_port, api_port = resolve_ports(args.ui_port, args.api_port)
    if api_port == ui_port:
        api_port = ui_port + 1
    _check_port(ui_port, "UI")
    _check_port(api_port, "API")

    if args.save_ports:
        _save_ports(ui_port, api_port)
    if args.https:
        _ensure_certs()

    _print_access(ui_port, api_port, use_https=args.https)

    ui = subprocess.Popen(_streamlit_cmd(ui_port, args.https))
    api = subprocess.Popen(_uvicorn_cmd(api_port, args.https))
    bonjour = None
    bonjour_script = ROOT / "scripts" / "bonjour_advertise.py"
    if bonjour_script.exists():
        bonjour = subprocess.Popen([_python(), str(bonjour_script)])

    try:
        ui.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if bonjour:
            bonjour.terminate()
        ui.terminate()
        api.terminate()


def cmd_set_ports(args):
    ui_port, api_port = resolve_ports(args.ui_port, args.api_port)
    _check_port(ui_port, "UI")
    _check_port(api_port, "API")
    _save_ports(ui_port, api_port)
    ip = local_ip()
    print(f"   iPhone will use: http://{ip}:{ui_port}")


def cmd_report(_args):
    subprocess.check_call([_python(), str(ROOT / "scripts" / "generate_report.py")])


def cmd_instructions(_args):
    subprocess.check_call([_python(), str(ROOT / "scripts" / "create_instructions.py")])


def main():
    parser = argparse.ArgumentParser(prog="growth", description="Plant digital twin — independent app")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", help="Create venv and install dependencies")

    p_serve = sub.add_parser("serve", help="Run Streamlit UI")
    p_serve.add_argument("--port", type=int, help="UI port (overrides config/env)")
    p_serve.add_argument("--save-ports", action="store_true", help="Persist chosen port(s) to config.json")
    p_serve.add_argument("--https", action="store_true", help="Use HTTPS (fixes iPhone Safari HTTPS-Only)")

    p_api = sub.add_parser("api", help="Run REST API")
    p_api.add_argument("--port", type=int, help="API port (overrides config/env)")
    p_api.add_argument("--save-ports", action="store_true", help="Persist chosen port(s) to config.json")
    p_api.add_argument("--https", action="store_true", help="Use HTTPS")

    p_start = sub.add_parser("start", help="Run UI + API")
    p_start.add_argument("--ui-port", type=int, help=f"UI port (default {DEFAULT_UI_PORT})")
    p_start.add_argument("--api-port", type=int, help=f"API port (default {DEFAULT_API_PORT})")
    p_start.add_argument("--save-ports", action="store_true", help="Persist chosen ports to config.json")
    p_start.add_argument("--https", action="store_true", help="Use HTTPS (fixes iPhone Safari HTTPS-Only)")

    p_ports = sub.add_parser("set-ports", help="Save ports to config.json without starting")
    p_ports.add_argument("--ui-port", type=int, required=True)
    p_ports.add_argument("--api-port", type=int, required=True)

    sub.add_parser("report", help="Generate status report")
    sub.add_parser("instructions", help="Generate care instructions")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        print()
        print("Examples:")
        print("  ./run.sh --https                    # iPhone Safari (HTTPS-Only)")
        print("  ./run.sh --ui-port 21322 --save-ports")
        print("  GROWTH_UI_PORT=21322 ./run.sh")
        return

    handlers = {
        "install": cmd_install,
        "serve": cmd_serve,
        "api": cmd_api,
        "start": cmd_start,
        "set-ports": cmd_set_ports,
        "report": cmd_report,
        "instructions": cmd_instructions,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
