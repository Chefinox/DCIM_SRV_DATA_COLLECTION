import sys
import re

for filepath in sys.argv[1:]:
    with open(filepath, 'r') as f:
        content = f.read()

    if 'from src.observability.logging.dcim_logger import setup_logger' in content:
        continue

    basename = filepath.split('/')[-1].replace('.py', '')

    # Insert imports
    imports = f"""
import sys
if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
logger = setup_logger("{basename}", "/home/infra/dcim_metrics_project/logs/{basename}.log")
"""
    
    # insert after the first block of imports
    if 'import json' in content:
        content = content.replace('import json', 'import json' + imports, 1)
    else:
        content = imports + "\n" + content

    # Replace print("Error...") with logger.error
    content = re.sub(r'print\(\s*[f]?["\']Error\s+(.*?)\)', r'logger.error(f"Error \1")', content)
    # Replace print(f"Error...") with logger.error
    content = re.sub(r'print\(\s*f["\']Error([^"\']*)["\']\s*\)', r'logger.error(f"Error\1")', content)
    # Replace other prints with logger.info
    content = re.sub(r'print\((.*?)\)', r'logger.info(\1)', content)

    with open(filepath, 'w') as f:
        f.write(content)
    print(f"Updated {filepath}")
