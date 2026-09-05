import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

# Replace the overlays check
old_check = r'''            if \(Settings\.canDrawOverlays\(requireContext\(\)\)\) \{
                val intent = Intent\(requireContext\(\), com\.deniscerri\.ytdl\.service\.FloatingPlayerService::class\.java\)
                intent\.putStringArrayListExtra\("URLS", ArrayList\(streamUrls\)\)
                val currentPos = videoView\.player\?\.currentPosition \?: 0L
                intent\.putExtra\("POSITION", currentPos\)
                if \(Build\.VERSION\.SDK_INT >= Build\.VERSION_CODES\.O\) \{
                    requireContext\(\)\.startForegroundService\(intent\)
                \} else \{
                    requireContext\(\)\.startService\(intent\)
                \}
            \} else \{
                val intent = Intent\(Settings\.ACTION_MANAGE_OVERLAY_PERMISSION, Uri\.parse\("package:\$\{requireContext\(\)\.packageName\}"\)\)
                startActivity\(intent\)
            \}'''

new_check = r'''            val intent = Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java)
            intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))
            val currentPos = videoView.player?.currentPosition ?: 0L
            intent.putExtra("POSITION", currentPos)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                requireContext().startForegroundService(intent)
            } else {
                requireContext().startService(intent)
            }'''

text = re.sub(old_check, new_check, text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(text)
