with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

import re

# We see that we accidentally inserted the new block, and the old block is still there partially.
# Let's just find the exact text we inserted and the leftovers and replace it cleanly.
# The `pipButton.setOnClickListener` starts at 162.

# Best way is to find the original file or just do a regex that actually captures the outer braces properly, 
# or since I know what's there, I'll extract everything before `pipButton.setOnClickListener {` and everything after `val title = view.findViewById<TextView>(R.id.title)`

start_idx = text.find('pipButton.setOnClickListener {')
end_idx = text.find('val title = view.findViewById<TextView>(R.id.title)')

new_block = """pipButton.setOnClickListener {
            if (streamUrls == null) {
                android.widget.Toast.makeText(requireContext(), "Loading video stream, please wait...", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (Build.VERSION.SDK_INT >= 33 && requireContext().checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 101)
                android.widget.Toast.makeText(requireContext(), "Please grant notification permission for background play.", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (Settings.canDrawOverlays(requireContext())) {
                val intent = Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java)
                intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))
                val currentPos = videoView.player?.currentPosition ?: 0L
                intent.putExtra("POSITION", currentPos)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    requireContext().startForegroundService(intent)
                } else {
                    requireContext().startService(intent)
                }
            } else {
                android.widget.Toast.makeText(requireContext(), "Please grant display over other apps for mini player.", android.widget.Toast.LENGTH_SHORT).show()
                val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, android.net.Uri.parse("package:" + requireContext().packageName))
                startActivity(intent)
            }
        }

        """

if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + new_block + text[end_idx:]
    with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
        f.write(text)
    print("Fixed dialog!")
else:
    print("Could not find bounds.")

