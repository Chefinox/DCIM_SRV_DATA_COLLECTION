import subprocess
print("=== dcim-es-consumer ===")
print(subprocess.run(["journalctl", "-u", "dcim-es-consumer.service", "--no-pager", "-n", "20"], capture_output=True, text=True).stdout)
print("=== dcim-itop-unified ===")
print(subprocess.run(["journalctl", "-u", "dcim-itop-unified.service", "--no-pager", "-n", "20"], capture_output=True, text=True).stdout)
print("=== dcim-sql-consumer ===")
print(subprocess.run(["journalctl", "-u", "dcim-sql-consumer.service", "--no-pager", "-n", "20"], capture_output=True, text=True).stdout)
