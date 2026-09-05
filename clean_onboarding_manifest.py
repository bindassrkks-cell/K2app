import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    xml = f.read()

onboarding_block = """        <activity
            android:name=".OnboardingActivity"
            android:exported="true"
            android:theme="@style/Theme.YTDL">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>"""

clean_onboarding_block = """        <activity
            android:name=".OnboardingActivity"
            android:exported="true"
            android:theme="@style/Theme.YTDL">
        </activity>"""

xml = xml.replace(onboarding_block, clean_onboarding_block)

with open('app/src/main/AndroidManifest.xml', 'w') as f:
    f.write(xml)
