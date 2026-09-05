import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    content = f.read()

# Add permissions
perms = """
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
"""
content = re.sub(r'<application', perms + '\n    <application', content)

# Add service
service = """
        <service
            android:name=".service.FloatingPlayerService"
            android:foregroundServiceType="mediaPlayback"
            android:exported="false" />
"""
content = re.sub(r'</application>', service + '\n    </application>', content)

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(content)
