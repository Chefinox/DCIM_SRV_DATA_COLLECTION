import subprocess
print(subprocess.run(["journalctl", "-u", "dcim-normalizer.service", "--no-pager", "-n", "20"], capture_output=True, text=True).stdout)
