import nipyapi
import time
import requests
import sys

requests.packages.urllib3.disable_warnings()

print("Waiting for NiFi to be ready...")
max_retries = 30
for i in range(max_retries):
    try:
        res = requests.get("https://localhost:8443/nifi-api/access/config", verify=False, timeout=5)
        if res.status_code == 200:
            print("NiFi API is reachable.")
            break
    except Exception:
        pass
    print(f"Waiting ({i+1}/{max_retries})...")
    time.sleep(10)

nipyapi.config.nifi_config.host = 'https://localhost:8443/nifi-api'
nipyapi.config.nifi_config.verify_ssl = False
nipyapi.security.service_login(service='nifi', username='admin', password='Inovasi@0918')

processors = [
    {'name': 'Run server_inventory_collector', 'old': '/opt/nifi/nifi-current/server_inventory_collector.py', 'new': '/opt/nifi/nifi-current/scripts/server_inventory_collector.py'},
    {'name': 'ExecuteProcess', 'old': '/opt/nifi/nifi-current/redfish_poller.py', 'new': '/opt/nifi/nifi-current/scripts/redfish_poller.py'},
    {'name': 'ExecuteProcess', 'old': '/opt/nifi/nifi-current/mikrotik_poller.py', 'new': '/opt/nifi/nifi-current/scripts/mikrotik_poller.py'},
    {'name': 'ExecuteProcess', 'old': '/opt/nifi/nifi-current/nas_poller.py', 'new': '/opt/nifi/nifi-current/scripts/nas_poller.py'},
    {'name': 'ExecuteProcess', 'old': '/opt/nifi/nifi-current/snmp_ups_poller.py', 'new': '/opt/nifi/nifi-current/scripts/snmp_ups_poller.py'},
    {'name': 'ExecuteProcess', 'old': '/opt/nifi/nifi-current/cctv_poller.py', 'new': '/opt/nifi/nifi-current/scripts/cctv_poller.py'}
]

def update_all_processors():
    all_procs = nipyapi.canvas.list_all_processors()
    count = 0
    for proc in all_procs:
        if proc.component.type == 'org.apache.nifi.processors.standard.ExecuteProcess':
            args = proc.component.config.properties.get('Command Arguments')
            if args:
                for target in processors:
                    if args == target['old']:
                        print(f"Updating processor '{proc.component.name}' ID: {proc.id}")
                        was_running = False
                        if proc.status.run_status == 'Running':
                            nipyapi.canvas.schedule_processor(proc, False)
                            was_running = True
                            time.sleep(2)
                            
                        # Update configuration
                        nipyapi.canvas.update_processor(
                            proc,
                            nipyapi.nifi.ProcessorConfigDTO(
                                properties={'Command Arguments': target['new']}
                            )
                        )
                        print(f"  -> Path changed to {target['new']}")
                        count += 1
                        
                        if was_running:
                            time.sleep(1)
                            nipyapi.canvas.schedule_processor(proc, True)
    print(f"Updated {count} processors.")

if __name__ == "__main__":
    update_all_processors()
