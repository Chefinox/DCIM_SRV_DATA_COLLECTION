import json, gzip

with gzip.open('nifi/flow.json.gz', 'rt') as f:
    data = json.load(f)

def find_processors(pg, name_match):
    found = []
    if 'processors' in pg:
        for p in pg['processors']:
            if name_match.lower() in p['type'].lower() or name_match.lower() in p['name'].lower():
                found.append(p)
    if 'processGroups' in pg:
        for child in pg['processGroups']:
            found.extend(find_processors(child, name_match))
    return found

root = data['rootGroup']
publishers = find_processors(root, 'PublishKafka')
for p in publishers:
    print(f"Name: {p['name']}")
    print(f"Topic: {p.get('properties', {}).get('topic', 'N/A')}")
    print(f"Brokers: {p.get('properties', {}).get('bootstrap.servers', 'N/A')}")
    print(f"Security: {p.get('properties', {}).get('security.protocol', 'N/A')}")
    print("-" * 40)
