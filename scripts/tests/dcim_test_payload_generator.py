import json
import time
import argparse
import random
from kafka import KafkaProducer

def main():
    parser = argparse.ArgumentParser(description='DCIM Test Payload Generator')
    parser.add_argument('--rate', type=int, default=10, help='Messages per second')
    parser.add_argument('--duration', type=int, default=10, help='Duration in seconds')
    parser.add_argument('--topic', type=str, default='dcim.raw.network.interfaces', help='Kafka topic')
    parser.add_argument('--bootstrap', type=str, default='localhost:9092', help='Kafka bootstrap server')
    args = parser.parse_args()

    producer = KafkaProducer(
        bootstrap_servers=[args.bootstrap],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    print(f"Starting load test: {args.rate} msg/s for {args.duration}s to topic {args.topic}")
    
    total_messages = args.rate * args.duration
    start_time = time.time()
    
    for i in range(total_messages):
        # Throttle to maintain rate
        elapsed = time.time() - start_time
        expected_sent = i + 1
        current_rate_delay = (expected_sent / args.rate) - elapsed
        if current_rate_delay > 0:
            time.sleep(current_rate_delay)

        sn_id = (i % 50) + 1
        payload = {
            "name": "server_redfish",
            "timestamp": int(time.time()),
            "tags": {
                "hostname": f"TEST-SRV-{sn_id:03d}",
                "serial_number": f"TEST-SN-{sn_id:03d}",
                "ip": f"10.200.0.{sn_id}",
                "device_type": "server"
            },
            "fields": {
                "reading_celsius": random.randint(20, 45),
                "power_watts": random.randint(100, 500)
            }
        }
        
        producer.send(args.topic, payload)
        
        if (i + 1) % args.rate == 0:
            print(f"Sent {i + 1} messages...")

    producer.flush()
    print(f"Finished. Total sent: {total_messages}")

if __name__ == "__main__":
    main()
