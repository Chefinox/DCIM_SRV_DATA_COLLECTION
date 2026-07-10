import subprocess
print("Checking Kafka...")
res = subprocess.run(["docker", "exec", "kafka1", "/opt/kafka/bin/kafka-run-class.sh", "kafka.tools.GetOffsetShell", "--broker-list", "localhost:9092", "--topic", "dcim.raw.storage.nas"], capture_output=True, text=True)
print(res.stdout)
