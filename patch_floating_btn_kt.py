import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

kt_code = """
        val pipButton = view.findViewById<View>(R.id.pip_button)
        pipButton.setOnClickListener {
            if (Settings.canDrawOverlays(requireContext())) {
                val intent = Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java)
                intent.putExtra("URL", item.url)
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
    r'val downloadThumb = view\.findViewById<Button>\(R\.id\.download_thumb\)',
    'val downloadThumb = view.findViewById<Button>(R.id.download_thumb)\n' + kt_code,
    content
)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)
