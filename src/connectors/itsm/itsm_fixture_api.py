from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import uuid
import re

class ITSMFixtureHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_POST(self):
        # Simulate ServiceNow/Jira Incident Creation API
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))
        
        path = self.path
        
        if '/api/now/table/incident' in path:
            # ServiceNow Simulation
            print(f"[ServiceNow Mock] Creating incident: {payload.get('short_description')}")
            response = {
                "result": {
                    "sys_id": str(uuid.uuid4()),
                    "number": f"INC{str(uuid.uuid4().int)[:7]}",
                    "short_description": payload.get('short_description'),
                    "state": "New"
                }
            }
            self._set_headers(201)
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        elif '/rest/api/2/issue' in path:
            # Jira Simulation
            print(f"[Jira Mock] Creating issue: {payload.get('fields', {}).get('summary')}")
            response = {
                "id": str(uuid.uuid4().int)[:5],
                "key": f"DCIM-{str(uuid.uuid4().int)[:4]}",
                "self": f"http://localhost:8083/rest/api/2/issue/{str(uuid.uuid4().int)[:5]}"
            }
            self._set_headers(201)
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not Found"}')

def run_server(port=8083):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ITSMFixtureHandler)
    print(f"Starting ITSM Fixture Adapter (Mock API) on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Stopping Mock API.")

if __name__ == '__main__':
    run_server()
