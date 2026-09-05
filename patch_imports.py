import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

imports = """
import android.content.Intent
import android.provider.Settings
import android.os.Build
"""
content = re.sub(r'import android.os.Bundle', imports + '\nimport android.os.Bundle', content)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)

