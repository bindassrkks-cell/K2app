import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    kt = f.read()

# Make PendingIntent send an action to the service instead of just launching MainActivity?
# Actually, if it launches MainActivity, we can just intercept onStartCommand with an action.
# But MediaSession.Builder's sessionActivity expects an activity Intent.
session_setup = """
        val intent = Intent(this, MainActivity::class.java)
        intent.flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        mediaSession = MediaSession.Builder(this, player!!).setSessionActivity(pendingIntent).build()
"""
kt = re.sub(r'val intent = Intent\(this, MainActivity::class\.java\)\n\s*val pendingIntent = PendingIntent\.getActivity\(this, 0, intent, PendingIntent\.FLAG_IMMUTABLE\)\n\s*mediaSession = MediaSession\.Builder\(this, player!!\)\.setSessionActivity\(pendingIntent\)\.build\(\)', session_setup.strip(), kt)

# If the floating view is removed, we want to add it back if they click the logo or start the service again.
# But we removed it in the X button. Let's make the X button just call stopSelf() to terminate the PiP fully, as is standard.
close_btn_handler = """
        closeBtn.setOnClickListener { 
            stopSelf()
        }
"""
kt = re.sub(r'closeBtn\.setOnClickListener \{ \n\s*if \(floatingView\.parent != null\) \{\n\s*windowManager\.removeView\(floatingView\)\n\s*\}\n\s*\}', close_btn_handler.strip(), kt)

# Ensure windowManager removeView doesn't crash on onDestroy if it was already removed
kt = kt.replace('windowManager.removeView(floatingView)', 'if (floatingView.parent != null) windowManager.removeView(floatingView)')

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(kt)

