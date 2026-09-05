import re
with open('app/src/main/res/layout/fragment_home.xml', 'r') as f:
    xml = f.read()

xml = xml.replace('android:textColor="#000000"', 'android:textColor="@color/home_title_text_color"')
xml = xml.replace('android:textColor="#FF0000"', 'android:textColor="@color/home_beta_text_color"')

with open('app/src/main/res/layout/fragment_home.xml', 'w') as f:
    f.write(xml)
