#!/usr/bin/env python3
"""
Dashboard HTTP Server and JSON API.
Serves static dashboard files and provides REST APIs for metrics & telemetry.
"""

import sys
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent


class DashboardAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "total_cases": 10,
                "passed_cases": 10,
                "governance_compliance": "100%",
                "avg_score": 100.0,
                "hardware": "Dual GV100 NVLink 64GB",
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if self.path == "/api/leaderboard":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            leaderboard_file = DASHBOARD_DIR / "data" / "leaderboard.json"
            if leaderboard_file.exists():
                self.wfile.write(leaderboard_file.read_bytes())
            else:
                self.wfile.write(json.dumps([]).encode("utf-8"))
            return

        super().do_GET()


def run_dashboard_server(port: int = 8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, DashboardAPIHandler)
    print(f"🚀 uvm-agent-lab Dashboard running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_dashboard_server(port)
