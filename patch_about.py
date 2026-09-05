import re
with open('app/src/main/res/layout/dialog_about_app.xml', 'r') as f:
    xml = f.read()

xml = re.sub(r'<ImageView.*?/>', '', xml, flags=re.DOTALL)

with open('app/src/main/res/layout/dialog_about_app.xml', 'w') as f:
    f.write(xml)
