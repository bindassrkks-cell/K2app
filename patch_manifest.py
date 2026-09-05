import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    xml = f.read()

# Change launcher from MainActivity to OnboardingActivity
xml = xml.replace('<action android:name="android.intent.action.MAIN" />', '')
xml = xml.replace('<category android:name="android.intent.category.LAUNCHER" />', '')

onboarding_activity = """
        <activity
            android:name=".OnboardingActivity"
            android:exported="true"
            android:theme="@style/Theme.YTDL">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
"""

xml = re.sub(r'(<application.*?>)', r'\1' + onboarding_activity, xml, flags=re.DOTALL)

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(xml)

