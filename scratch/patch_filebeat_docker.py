import yaml
import sys
import os

CONFIG_PATH = '/tmp/filebeat_orig.yml'

with open(CONFIG_PATH, 'r') as f:
    content = f.read()

# Add container input for Docker logs if not exists
if 'id: dcim-docker-logs' not in content:
    input_block = """
- type: container
  id: dcim-docker-logs
  enabled: true
  paths:
    - /var/lib/docker/containers/*/*.log
"""
    # Find the inputs section and append
    content = content.replace('filebeat.inputs:', 'filebeat.inputs:' + input_block)

with open('/tmp/new_filebeat.yml', 'w') as f:
    f.write(content)
print("Created /tmp/new_filebeat.yml")
