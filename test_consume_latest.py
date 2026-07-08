from kafka import KafkaConsumer
import uuid
consumer = KafkaConsumer('dcim.raw.network.snmp', bootstrap_servers='127.0.0.1:9092', group_id=str(uuid.uuid4()), auto_offset_reset='latest', consumer_timeout_ms=70000)
for msg in consumer:
    print(msg.value.decode('utf-8'))
    break
