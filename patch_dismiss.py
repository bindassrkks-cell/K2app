import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

# Replace trailing dismiss() with nothing if it was part of navigation
text = text.replace('this.dismiss()', '')
text = text.replace('dismiss()\n', '\n')
text = text.replace('dismiss()', '')

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(text)

