import json

def find_text_layers(data):
    if isinstance(data, dict):
        if data.get('ty') == 't' or data.get('t') is not None and isinstance(data.get('t'), dict) and 'd' in data.get('t'):
            print("Found text layer!")
            print(data)
        for k, v in data.items():
            find_text_layers(v)
    elif isinstance(data, list):
        for item in data:
            find_text_layers(item)

with open('app/src/main/res/raw/welcome.json', 'r') as f:
    find_text_layers(json.load(f))
