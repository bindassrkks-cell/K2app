import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    xml = f.read()

new_service = """
        <service
            android:name=".service.FloatingPlayerService"
            android:foregroundServiceType="mediaPlayback"
            android:exported="true">
            <intent-filter>
                <action android:name="androidx.media3.session.MediaSessionService" />
            </intent-filter>
        </service>
"""

xml = re.sub(r'<service.*?android:name="\.service\.FloatingPlayerService".*?/>', new_service.strip(), xml, flags=re.DOTALL)

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(xml)

