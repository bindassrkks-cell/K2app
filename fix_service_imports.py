with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    text = f.read()

text = text.replace('import androidx.media3.session.SessionCommand', 'import androidx.media3.session.SessionCommand\nimport androidx.media3.session.SessionResult')
text = text.replace('MediaSession.SessionResult', 'SessionResult')

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(text)
