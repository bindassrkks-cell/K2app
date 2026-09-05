import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    text = f.read()

# Remove UI related imports
text = re.sub(r'import android\.graphics\.PixelFormat\n', '', text)
text = re.sub(r'import android\.view\..*?\n', '', text)
text = re.sub(r'import android\.widget\..*?\n', '', text)

# Remove windowManager, floatingView, isCollapsed
text = re.sub(r'private lateinit var windowManager: WindowManager\n', '', text)
text = re.sub(r'private lateinit var floatingView: View\n', '', text)
text = re.sub(r'private var isCollapsed = false\n', '', text)

# Remove setupFloatingWindow call and definition
text = text.replace('windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager\n        setupFloatingWindow()', 'setupBackgroundPlayer()')

setup_bg_player = '''
    private fun setupBackgroundPlayer() {
        player = ExoPlayer.Builder(this).build()
        val intent = Intent(this, MainActivity::class.java)
        intent.putExtra("RESTORE_PLAYER", true)
        intent.flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        mediaSession = MediaSession.Builder(this, player!!).setSessionActivity(pendingIntent).build()
    }
'''

text = re.sub(r'private fun setupFloatingWindow\(\) \{.*?\}\n\n    private fun playVideo', setup_bg_player + '\n    private fun playVideo', text, flags=re.DOTALL)

# Remove windowManager references in onDestroy
text = re.sub(r'if \(floatingView\.parent != null\) \{.*?\windowManager\.removeView\(floatingView\)\n        \}', '', text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(text)

