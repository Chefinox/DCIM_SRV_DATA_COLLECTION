import sys
import os
import re

def process_file(filepath):
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
        if 'logging.basicConfig' not in content and 'logger = logging.getLogger' not in content:
            return
            
        if 'from src.observability.logging.dcim_logger import setup_logger' in content:
            return

        # Add imports
        content = re.sub(r'(import logging)', r'\1\nimport sys\nif "/home/infra/dcim_metrics_project" not in sys.path:\n    sys.path.append("/home/infra/dcim_metrics_project")\nfrom src.observability.logging.dcim_logger import setup_logger', content, count=1)
        
        # Replace basicConfig
        basename = os.path.basename(filepath).replace('.py', '')
        # Try to find log file in basicConfig
        log_file_match = re.search(r'filename=[\'"]([^\'"]+)[\'"]|filename=([A-Z_]+)', content)
        log_file = "None"
        if log_file_match:
            val = log_file_match.group(1) or log_file_match.group(2)
            if not val.isupper():
                log_file = f'"{val}"'
            else:
                log_file = val

        # Replace basicConfig block
        content = re.sub(r'logging\.basicConfig\([^)]+\)', f'logger = setup_logger("{basename}", {log_file})', content)
        
        # Replace logger = logging.getLogger(...)
        content = re.sub(r'logger\s*=\s*logging\.getLogger\([^\)]+\)', f'logger = setup_logger("{basename}", {log_file})', content)
        
        # Some scripts just use logging.info, which works if we replace logging with logger but it's tricky.
        # So we also do: logging = logger
        content = re.sub(r'(logger = setup_logger\([^)]+\))', r'\1\nlogging = logger', content)
        
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

for filepath in sys.argv[1:]:
    process_file(filepath)
