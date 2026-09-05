import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    kt = f.read()

kt = kt.replace('private var player: ExoPlayer? = null', 'var player: ExoPlayer? = null')

# Add companion object
companion = """
    companion object {
        var instance: FloatingPlayerService? = null
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
"""
kt = kt.replace('    override fun onCreate() {\n        super.onCreate()', companion)

kt = kt.replace('        super.onDestroy()\n    }', '        instance = null\n        super.onDestroy()\n    }')

# Set intent to RESTORE_PLAYER
kt = kt.replace('val intent = Intent(this, MainActivity::class.java)', 'val intent = Intent(this, MainActivity::class.java)\n        intent.putExtra("RESTORE_PLAYER", true)')

# Metadata for MediaItem
media_item_replace = """        if (urls.size == 2) {
            val audioItem = MediaItem.Builder().setUri(Uri.parse(urls[0])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            val videoItem = MediaItem.Builder().setUri(Uri.parse(urls[1])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            val audioSource: MediaSource =
                DefaultMediaSourceFactory(this).createMediaSource(audioItem)
            val videoSource: MediaSource =
                DefaultMediaSourceFactory(this).createMediaSource(videoItem)
            player?.setMediaSource(MergingMediaSource(videoSource, audioSource))
        } else if (urls.isNotEmpty()) {
            val item = MediaItem.Builder().setUri(Uri.parse(urls[0])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            player?.addMediaItem(item)
        }"""
        
# Find the exact lines to replace
import re
pattern = r'if \(urls.size == 2\) \{.*?player\?\.addMediaItem\(MediaItem\.fromUri\(Uri\.parse\(urls\[0\]\)\)\)\n        \}'
kt = re.sub(pattern, media_item_replace, kt, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(kt)
