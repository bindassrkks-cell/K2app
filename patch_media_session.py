import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    content = f.read()

# Add MediaSession imports
imports = """
import androidx.media3.session.MediaSession
"""
content = re.sub(r'import androidx.media3.exoplayer.ExoPlayer', imports + '\nimport androidx.media3.exoplayer.ExoPlayer', content)

# Add MediaSession property
content = re.sub(
    r'private var isCollapsed = false',
    'private var isCollapsed = false\n    private var mediaSession: MediaSession? = null',
    content
)

# Initialize MediaSession
setup_session = """
        player = ExoPlayer.Builder(this).build()
        mediaSession = MediaSession.Builder(this, player!!).build()
        playerView.player = player
"""
content = re.sub(
    r'player = ExoPlayer\.Builder\(this\)\.build\(\)\n\s*playerView\.player = player',
    setup_session.strip(),
    content
)

# Release MediaSession
release_session = """
        mediaSession?.release()
        player?.release()
"""
content = re.sub(
    r'player\?\.release\(\)',
    release_session.strip(),
    content
)

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(content)

