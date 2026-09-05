import re

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'r') as f:
    kt = f.read()

close_btn = """
        closeBtn.setOnClickListener {
            if (floatingView.parent != null) {
                windowManager.removeView(floatingView)
            }
        }
"""
kt = kt.replace('closeBtn.setOnClickListener {\n            stopSelf()\n        }', close_btn.strip())

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(kt)

