import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    kt = f.read()

# Add position passing to Intent
old_intent = 'intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))'
new_intent = """
                intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))
                val currentPos = videoView.player?.currentPosition ?: 0L
                intent.putExtra("POSITION", currentPos)
"""
kt = kt.replace(old_intent, new_intent.strip())

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(kt)

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    kt_service = f.read()

# Receive position and seek
old_play = 'playVideo(urls)'
new_play = """
        val position = intent?.getLongExtra("POSITION", 0L) ?: 0L
        playVideo(urls, position)
"""
kt_service = kt_service.replace(old_play, new_play.strip())

old_play_def = 'private fun playVideo(urls: List<String>) {'
new_play_def = 'private fun playVideo(urls: List<String>, position: Long) {'
kt_service = kt_service.replace(old_play_def, new_play_def)

old_play_prepare = 'player?.prepare()'
new_play_prepare = """
        if (position > 0L) {
            player?.seekTo(position)
        }
        player?.prepare()
"""
kt_service = kt_service.replace(old_play_prepare, new_play_prepare.strip())

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(kt_service)

