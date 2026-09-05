import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

gesture_imports = """
import android.media.AudioManager
import android.provider.Settings
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.WindowManager
import kotlin.math.abs
"""

content = content.replace('import android.os.Bundle', gesture_imports + 'import android.os.Bundle')

gesture_code = """
        // Gesture controls for brightness and volume
        val audioManager = requireContext().getSystemService(android.content.Context.AUDIO_SERVICE) as AudioManager
        val gestureDetector = GestureDetector(requireContext(), object : GestureDetector.SimpleOnGestureListener() {
            private var isVolume = false
            private var startY = 0f
            private var startVolume = 0
            private var startBrightness = 0f

            override fun onDown(e: MotionEvent): Boolean {
                val width = videoView.width
                isVolume = e.x > width / 2f
                startY = e.y
                if (isVolume) {
                    startVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                } else {
                    val window = dialog?.window
                    startBrightness = window?.attributes?.screenBrightness ?: -1f
                    if (startBrightness < 0) {
                        try {
                            startBrightness = Settings.System.getInt(requireContext().contentResolver, Settings.System.SCREEN_BRIGHTNESS) / 255f
                        } catch (e: Exception) {}
                    }
                }
                return true
            }

            override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
                if (e1 == null) return false
                val deltaY = e1.y - e2.y
                val height = videoView.height
                val percent = deltaY / height

                if (isVolume) {
                    val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                    val change = (percent * maxVolume).toInt()
                    val newVolume = (startVolume + change).coerceIn(0, maxVolume)
                    audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, newVolume, AudioManager.FLAG_SHOW_UI)
                } else {
                    val change = percent
                    val newBrightness = (startBrightness + change).coerceIn(0f, 1f)
                    val window = dialog?.window
                    val layoutParams = window?.attributes
                    layoutParams?.screenBrightness = newBrightness
                    window?.attributes = layoutParams
                }
                return true
            }
        })

        videoView.setOnTouchListener { _, event ->
            gestureDetector.onTouchEvent(event)
            false
        }
"""

content = content.replace('val loading = view.findViewById<ProgressBar>(R.id.loading)', gesture_code + '\n        val loading = view.findViewById<ProgressBar>(R.id.loading)')

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)
