import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

content = re.sub(r'import android\.provider\.Settings\n', '', content)
content = re.sub(r'import android\.os\.Build\n', '', content)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write('import android.provider.Settings\nimport android.os.Build\n' + content)
