import json
with open('metadata.json', 'r') as f:
    data = json.load(f)

data['name'] = "Kupido2"
data['description'] = "Kupido player 2 Beta"

with open('metadata.json', 'w') as f:
    json.dump(data, f, indent=2)
