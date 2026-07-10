import nipyapi
import sys

# Setup auth
nipyapi.config.nifi_config.host = 'https://localhost:8443/nifi-api'
nipyapi.config.nifi_config.verify_ssl = False
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    nipyapi.security.service_login(service='nifi', username='admin', password='Inovasi@0918')
except Exception as e:
    print(f"Login failed: {e}")
    sys.exit(1)


root_pg = nipyapi.canvas.get_process_group(nipyapi.canvas.get_root_pg_id(), 'id')

# Check if already exists
existing = nipyapi.canvas.get_process_group('Security SIEM Ingestion', 'name')
if existing:
    if isinstance(existing, list):
        existing = existing[0]
    print("Security SIEM Ingestion PG already exists. Deleting it first...")
    nipyapi.canvas.schedule_process_group(existing.id, False)
    nipyapi.canvas.delete_process_group(existing, force=True)

print("Creating PG...")
siem_pg = nipyapi.canvas.create_process_group(root_pg, 'Security SIEM Ingestion', (800, 200))

print("Creating ListenSyslog...")
listen_type = nipyapi.canvas.get_processor_type('ListenSyslog')
if not listen_type:
    listen_type = nipyapi.canvas.get_processor_type('org.apache.nifi.processors.standard.ListenSyslog')
if isinstance(listen_type, list): listen_type = listen_type[0]

listen_syslog = nipyapi.canvas.create_processor(
    siem_pg, listen_type, (400, 200), 'ListenSyslog - Wazuh',
    nipyapi.nifi.ProcessorConfigDTO(
        properties={
            'Port': '5140',
            'Protocol': 'TCP',
            'Parse Messages': 'true'
        }
    )
)

print("Creating PublishKafka_2_6...")
kafka_type = nipyapi.canvas.get_processor_type('PublishKafka_2_6')
if not kafka_type:
    kafka_type = nipyapi.canvas.get_processor_type('org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6')
if isinstance(kafka_type, list): kafka_type = kafka_type[0]

publish_kafka = nipyapi.canvas.create_processor(
    siem_pg, kafka_type, (400, 500), 'PublishKafka - SIEM Alerts',
    nipyapi.nifi.ProcessorConfigDTO(
        properties={
            'Kafka Brokers': 'kafka1:29092,kafka2:29095,kafka3:29097',
            'Topic Name': 'dcim.siem.alerts',
            'Use Transactions': 'false',
            'Delivery Guarantee': '1'
        }
    )
)

print("Connecting processors...")
# Connect success
nipyapi.canvas.create_connection(listen_syslog, publish_kafka, relationships=['success'])

# Auto terminate others
nipyapi.canvas.update_processor(
    listen_syslog,
    nipyapi.nifi.ProcessorConfigDTO(auto_terminated_relationships=['invalid'])
)
nipyapi.canvas.update_processor(
    publish_kafka,
    nipyapi.nifi.ProcessorConfigDTO(auto_terminated_relationships=['success', 'failure'])
)

print("Starting PG...")
nipyapi.canvas.schedule_process_group(siem_pg.id, True)
print("NiFi SIEM Ingestion Flow created and started successfully.")
