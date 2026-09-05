import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

replacement = """        pipButton.setOnClickListener {
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
        }"""

text = re.sub(r'pipButton\.setOnClickListener \{.*?\}\n', replacement + '\n', text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(text)
