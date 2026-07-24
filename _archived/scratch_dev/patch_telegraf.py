import re

with open('/etc/telegraf/telegraf.conf', 'r') as f:
    content = f.read()

# Comment out the legacy stream block
pattern = r'(# --- LEGACY STREAM.*?namedrop = \[.*?\]\n)'
def replacer(match):
    lines = match.group(1).split('\n')
    return '\n'.join(['#' + line if not line.startswith('#') and line.strip() else line for line in lines])

new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)

with open('/etc/telegraf/telegraf.conf', 'w') as f:
    f.write(new_content)
