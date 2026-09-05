import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

kt_code = """
        var streamUrls: List<String>? = null
        val pipButton = view.findViewById<View>(R.id.pip_button)
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
    r'val downloadThumb = view\.findViewById<MaterialButton>\(R\.id\.download_thumb\)',
    'val downloadThumb = view.findViewById<MaterialButton>(R.id.download_thumb)\n' + kt_code,
    content
)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)

