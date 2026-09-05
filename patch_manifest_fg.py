import xml.etree.ElementTree as ET
import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    xml_str = f.read()

# Add permissions if not present
perms = [
    '<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
    '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />',
    '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_SHORT_SERVICE" />'
]
for p in perms:
    if p not in xml_str:
        xml_str = xml_str.replace('<application', p + '\n    <application')

# Add SystemForegroundService definition
service_def = '''
        <service
            android:name="androidx.work.impl.foreground.SystemForegroundService"
            android:foregroundServiceType="dataSync|shortService"
            tools:node="merge" />
'''

if 'androidx.work.impl.foreground.SystemForegroundService' not in xml_str:
    xml_str = xml_str.replace('</application>', service_def + '</application>')
    
# Make sure tools namespace is there
if 'xmlns:tools="http://schemas.android.com/tools"' not in xml_str:
    xml_str = xml_str.replace('xmlns:android="http://schemas.android.com/apk/res/android"', 'xmlns:android="http://schemas.android.com/apk/res/android"\n    xmlns:tools="http://schemas.android.com/tools"')

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(xml_str)
