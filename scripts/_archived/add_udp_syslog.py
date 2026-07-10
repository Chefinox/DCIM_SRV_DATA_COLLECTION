import nipyapi
import sys
import urllib3
urllib3.disable_warnings()

nipyapi.config.nifi_config.host = 'https://localhost:8443/nifi-api'
nipyapi.config.nifi_config.verify_ssl = False
try:
    nipyapi.security.service_login(service='nifi', username='admin', password='Inovasi@0918')
except Exception as e:
    print(f"Login failed: {e}")
    sys.exit(1)

siem_pg = nipyapi.canvas.get_process_group('Security SIEM Ingestion', 'name')
if isinstance(siem_pg, list): siem_pg = siem_pg[0]

# Check if UDP listener already exists
udp_listener = nipyapi.canvas.get_processor('ListenSyslog - Wazuh UDP')
if not udp_listener:
    print("Creating UDP Listener...")
    listen_type = nipyapi.canvas.get_processor_type('org.apache.nifi.processors.standard.ListenSyslog')
    if isinstance(listen_type, list): listen_type = listen_type[0]

    listen_syslog_udp = nipyapi.canvas.create_processor(
        siem_pg, listen_type, (800, 200), 'ListenSyslog - Wazuh UDP',
        nipyapi.nifi.ProcessorConfigDTO(
            properties={
                'Port': '5140',
                'Protocol': 'UDP',
                'Parse Messages': 'true'
            }
        )
    )

    publish_kafka = nipyapi.canvas.get_processor('PublishKafka - SIEM Alerts')
    if isinstance(publish_kafka, list): publish_kafka = publish_kafka[0]

    # Connect to Kafka
    nipyapi.canvas.create_connection(listen_syslog_udp, publish_kafka, relationships=['success'])
    
    # Auto terminate invalid
    nipyapi.canvas.update_processor(
        listen_syslog_udp,
        nipyapi.nifi.ProcessorConfigDTO(auto_terminated_relationships=['invalid'])
    )

    nipyapi.canvas.schedule_processor(listen_syslog_udp, True)
    print("UDP Listener created and started.")
else:
    print("UDP Listener already exists.")
