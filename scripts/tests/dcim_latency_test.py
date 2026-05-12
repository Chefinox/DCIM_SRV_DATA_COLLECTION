import json
import time
import uuid
import argparse
from kafka import KafkaProducer, KafkaConsumer

def main():
    parser = argparse.ArgumentParser(description='DCIM End-to-End Latency Test')
    parser.add_argument('--count', type=int, default=10, help='Number of messages to test')
    parser.add_argument('--raw-topic', type=str, default='dcim.raw.network.interfaces', help='Input topic')
    parser.add_argument('--enriched-topic', type=str, default='dcim.enriched.events', help='Output topic')
    parser.add_argument('--bootstrap', type=str, default='localhost:9092', help='Kafka bootstrap')
    args = parser.parse_args()

    producer = KafkaProducer(
        bootstrap_servers=[args.bootstrap],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    consumer = KafkaConsumer(
        args.enriched_topic,
        bootstrap_servers=[args.bootstrap],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id=f'latency-test-group-{uuid.uuid4()}',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print(f"Starting latency test: {args.count} samples (Using REAL measurement: server_redfish)")
    time.sleep(2)

    latencies = []

    for i in range(args.count):
        trace_id = str(uuid.uuid4())[:8]
        test_hostname = f"LATENCY-TEST-{trace_id}"
        
        # Use server_redfish and temp_reading to ensure it passes through all filters
        payload = {
            "name": "server_redfish",
            "timestamp": int(time.time()),
            "tags": {
                "hostname": test_hostname,
                "serial_number": f"LATENCY-SN-{trace_id}",
                "device_type": "server",
                "site": "TEST-LAB"
            },
            "fields": {
                "temp_reading": 22.5,
                "trace_id": trace_id
            }
        }
        
        t1 = time.time()
        producer.send(args.raw_topic, payload)
        producer.flush()
        
        found = False
        timeout = 15
        wait_start = time.time()
        
        while time.time() - wait_start < timeout:
            msg_pack = consumer.poll(timeout_ms=500)
            for tp, messages in msg_pack.items():
                for msg in messages:
                    data = msg.value
                    h = data.get("hostname") or data.get("tags", {}).get("hostname")
                    if h == test_hostname:
                        t2 = time.time()
                        latency_ms = (t2 - t1) * 1000
                        latencies.append(latency_ms)
                        print(f"Sample {i+1}/{args.count}: {latency_ms:.2f} ms")
                        found = True
                        break
                if found: break
            if found: break
        
        if not found:
            print(f"Sample {i+1}/{args.count}: TIMEOUT after {timeout}s")
        
        time.sleep(0.5)

    if not latencies:
        print("FAIL: No samples captured.")
        return

    latencies.sort()
    p50 = latencies[len(latencies)//2]
    p95 = latencies[int(len(latencies)*0.95)]
    p99 = latencies[int(len(latencies)*0.99)]
    avg = sum(latencies) / len(latencies)

    print("\n=== LATENCY RESULTS ===")
    print(f"Samples: {len(latencies)}")
    print(f"Min:     {min(latencies):.2f} ms")
    print(f"Max:     {max(latencies):.2f} ms")
    print(f"Average: {avg:.2f} ms")
    print(f"p50:     {p50:.2f} ms")
    print(f"p95:     {p95:.2f} ms")
    print(f"p99:     {p99:.2f} ms")

if __name__ == "__main__":
    main()
