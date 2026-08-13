from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import uuid
from datetime import datetime, timezone
import random

class ProxmoxFixtureHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        # Simulate Proxmox VE API response for cluster resources (VMs)
        self._set_headers()
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Synthetic VM Data
        response_data = {
            "data": [
                {
                    "id": "qemu/100",
                    "type": "qemu",
                    "node": "pve-01",
                    "name": "PROD-SRV-WEB",
                    "status": "running",
                    "maxcpu": 4,
                    "cpu": random.uniform(0.1, 0.8),
                    "maxmem": 8589934592, # 8GB
                    "mem": random.uniform(2147483648, 6442450944),
                    "maxdisk": 53687091200, # 50GB
                    "disk": random.uniform(10737418240, 42949672960),
                    "uptime": random.randint(3600, 864000)
                },
                {
                    "id": "qemu/101",
                    "type": "qemu",
                    "node": "pve-01",
                    "name": "DEV-DB-01",
                    "status": "running",
                    "maxcpu": 2,
                    "cpu": random.uniform(0.05, 0.5),
                    "maxmem": 4294967296, # 4GB
                    "mem": random.uniform(1073741824, 3221225472),
                    "maxdisk": 107374182400, # 100GB
                    "disk": random.uniform(21474836480, 85899345920),
                    "uptime": random.randint(3600, 864000)
                },
                {
                    "id": "qemu/102",
                    "type": "qemu",
                    "node": "pve-02",
                    "name": "TEST-APP-01",
                    "status": "stopped",
                    "maxcpu": 2,
                    "cpu": 0.0,
                    "maxmem": 2147483648, # 2GB
                    "mem": 0,
                    "maxdisk": 21474836480, # 20GB
                    "disk": 0,
                    "uptime": 0
                }
            ]
        }
        
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

def run_server(port=8081):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ProxmoxFixtureHandler)
    print(f"Starting Proxmox Fixture Adapter (Mock API) on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Stopping Mock API.")

if __name__ == '__main__':
    run_server()
