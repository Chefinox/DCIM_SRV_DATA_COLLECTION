import sys
import os

filepath = sys.argv[1]
with open(filepath, 'r') as f:
    content = f.read()

# Replace the logging setup in dcim_threshold_alerter.py
if 'logging.basicConfig' in content:
    # Basic logic to replace logging.basicConfig with setup_logger
    import re
    # Find the imports
    content = re.sub(r'(import logging)', r'\1\nimport sys\nsys.path.append("/home/infra/dcim_metrics_project")\nfrom src.observability.logging.dcim_logger import setup_logger', content)
    
    # Find logging setup
    setup_pattern = r'LOG_FILE = [^\n]+\nlogging\.basicConfig\([\s\S]+?logging\.getLogger\(\'\'\)\.addHandler\(console\)'
    
    match = re.search(setup_pattern, content)
    if match:
        new_setup = """LOG_FILE = "/home/infra/dcim_metrics_project/logs/threshold_alerts.log"
logging = setup_logger("dcim-threshold-alerter", LOG_FILE)"""
        content = content[:match.start()] + new_setup + content[match.end():]
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated {filepath}")
    else:
        print(f"Pattern not found in {filepath}")
