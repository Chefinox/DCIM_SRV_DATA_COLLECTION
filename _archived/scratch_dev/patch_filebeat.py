import yaml
import sys
import os

CONFIG_PATH = '/tmp/filebeat_orig.yml'

with open(CONFIG_PATH, 'r') as f:
    content = f.read()

# Add filestream input for DCIM logs if not exists
if 'id: dcim-python-logs' not in content:
    input_block = """
- type: filestream
  id: dcim-python-logs
  enabled: true
  paths:
    - /home/infra/dcim_metrics_project/logs/*.log
    - /home/infra/dcim_metrics_project/scripts/*.log
  parsers:
    - ndjson:
        target: ""
        add_error_key: true
        overwrite_keys: true
        message_key: message
"""
    content = content.replace('filebeat.inputs:', 'filebeat.inputs:' + input_block)

# Change index pattern
if 'setup.template.name: "dcim-logs"' not in content:
    template_settings = """setup.template.name: "dcim-logs"
setup.template.pattern: "dcim-logs-*"
setup.template.settings:"""
    content = content.replace('setup.template.settings:', template_settings)

if 'index: "dcim-logs-%{+yyyy.MM.dd}"' not in content:
    import re
    content = re.sub(
        r'(output\.elasticsearch:[\s\S]*?hosts: \[[^\]]+\])',
        r'\1\n  index: "dcim-logs-%{+yyyy.MM.dd}"',
        content
    )
    if 'setup.ilm.enabled' not in content:
        content += "\nsetup.ilm.enabled: false\n"

with open('/tmp/new_filebeat.yml', 'w') as f:
    f.write(content)
print("Created /tmp/new_filebeat.yml")
