import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    content = f.read()

content = re.sub(r'import androidx\.media3\.session\.MediaSession\n', '', content)
content = re.sub(r'\s*private var mediaSession: MediaSession\? = null\n', '\n', content)
content = re.sub(r'\s*mediaSession = MediaSession\.Builder\(this, player!!\)\.build\(\)\n', '\n', content)
content = re.sub(r'\s*mediaSession\?\.release\(\)\n', '\n', content)

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(content)

