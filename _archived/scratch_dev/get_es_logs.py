import subprocess
print("=== dcim-es-consumer ===")
print(subprocess.run(["journalctl", "-u", "dcim-es-consumer.service", "--no-pager", "-n", "50"], capture_output=True, text=True).stdout)
