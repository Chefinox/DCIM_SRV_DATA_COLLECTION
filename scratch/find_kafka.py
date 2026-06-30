from confluent_kafka import Consumer, TopicPartition
import json

c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'debug-group-5',
    'auto.offset.reset': 'earliest'
})

topic = 'dcim.normalized.events'
c.assign([TopicPartition(topic, 0, 31030000)]) # Approximate offset from recent check

found = 0
while True:
    msg = c.poll(1.0)
    if msg is None:
        break
    if msg.error():
        continue
    
    val = msg.value().decode('utf-8')
    if "FIT-Core-RTR" in val:
        print(val)
        found += 1
        if found > 2:
            break
c.close()
