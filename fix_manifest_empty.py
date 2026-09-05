import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    xml = f.read()

# Restore MAIN/LAUNCHER to empty intent filters
main_filter = """
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
"""
xml = re.sub(r'<intent-filter>\s*</intent-filter>', main_filter.strip(), xml)

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(xml)

