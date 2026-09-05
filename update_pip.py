import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

# Replace the current pipButton listener
# We will just declare a mutable list for stream urls.
new_listener = """
        val pipButton = view.findViewById<View>(R.id.pip_button)
        var streamUrls: List<String>? = null
        pipButton.setOnClickListener {
            if (streamUrls == null) {
                android.widget.Toast.makeText(requireContext(), "Loading video stream, please wait...", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (Settings.canDrawOverlays(requireContext())) {
                val intent = Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java)
                intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    requireContext().startForegroundService(intent)
                } else {
                    requireContext().startService(intent)
                }
                dismiss()
            } else {
                val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, android.net.Uri.parse("package:" + requireContext().packageName))
                startActivity(intent)
            }
        }
"""

content = re.sub(
    r'val pipButton = view\.findViewById<View>\(R\.id\.pip_button\).*?startActivity\(intent\)\n        \}',
    new_listener.strip(),
    content,
    flags=re.DOTALL
)

# Set the stream urls once loaded
content = re.sub(
    r'val urls = data\.first',
    r'val urls = data.first\n                streamUrls = urls',
    content
)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)

