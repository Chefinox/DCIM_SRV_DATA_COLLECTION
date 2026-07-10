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
publishers = find_processors(root, 'Kafka')
for p in publishers:
    print(f"Name: {p['name']}, Type: {p['type']}")
