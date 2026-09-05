import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'r') as f:
    kt = f.read()

old_link = '• Room Database"'
new_link = '• Room Database<br><br>" +\n                "<b>General Guide:</b> <a href=\\"https://docs.google.com/document/d/1hIThBnHSi44u0Dnklc2ELCb2hUj3dSweCklTlJpMm7E/edit?usp=sharing\\">View Guide</a>"'
kt = kt.replace(old_link, new_link)

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'w') as f:
    f.write(kt)
