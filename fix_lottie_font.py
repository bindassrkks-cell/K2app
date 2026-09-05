import json

with open('app/src/main/res/raw/welcome.json', 'r') as f:
    data = json.load(f)

if 'fonts' in data:
    del data['fonts']
    print("Fonts removed")
        
with open('app/src/main/res/raw/welcome.json', 'w') as f:
    json.dump(data, f)
