import re

with open('app/src/main/AndroidManifest.xml', 'r') as f:
    content = f.read()

provider = """
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/provider_paths" />
        </provider>
"""

if "androidx.core.content.FileProvider" not in content:
    content = content.replace("</application>", provider + "\n    </application>")
    with open('app/src/main/AndroidManifest.xml', 'w') as f:
        f.write(content)
    print("Provider added")
else:
    print("Provider already exists")

