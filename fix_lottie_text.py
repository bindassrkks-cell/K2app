import json

def remove_text_layers(data):
    if isinstance(data, dict):
        if 'layers' in data:
            data['layers'] = [layer for layer in data['layers'] if layer.get('ty') != 5]
            for layer in data['layers']:
                remove_text_layers(layer)
        for k, v in data.items():
            if k != 'layers':
                remove_text_layers(v)
    elif isinstance(data, list):
        for item in data:
            remove_text_layers(item)

with open('app/src/main/res/raw/welcome.json', 'r') as f:
    data = json.load(f)

remove_text_layers(data)

with open('app/src/main/res/raw/welcome.json', 'w') as f:
    json.dump(data, f)
