import json
import time
from kafka import KafkaProducer

def main():
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    topic = "dcim.raw.device.isapi"
    print(f"Mengirim 10 data NVR ke topik {topic}...")
    
    for i in range(10):
        payload = {
            "name": "cctv_metrics",
            "timestamp": int(time.time()),
            "tags": {
                "hostname": "TEST-NVR-HQ",
                "serial_number": f"TEST-NVR-SN-999",
                "ip": "192.168.1.254",
                "device_type": "nvr"
            },
            "fields": {
                "status_online": 1,
                "status_text": "Online",
                "channelCount": 25,
                "recordingStatus": "Recording",
                "deviceName": "Main NVR Hikvision",
                "cpuUtilization": 40 + i,
                "memoryUsage": 60 + (i*2)
            }
        }
        
        producer.send(topic, payload)
        time.sleep(0.5)

    producer.flush()
    print("Selesai mengirim data NVR.")

if __name__ == "__main__":
    main()
