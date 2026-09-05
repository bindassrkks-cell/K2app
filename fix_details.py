import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

text = text.replace('class ResultCardDetailsDialog : BottomSheetDialogFragment', 'class ResultCardDetailsDialog : androidx.fragment.app.Fragment')

text = re.sub(r'override fun onCreateDialog\(.*?return dialog\n    \}', '', text, flags=re.DOTALL)

# Delete setupDialog block carefully
# It starts at:
#    @SuppressLint("RestrictedApi", "SetTextI18n", "UseGetLayoutInflater")
#    override fun setupDialog(dialog: Dialog, style: Int) {
# and ends before:
#    @androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
#    override fun onViewCreated

start_idx = text.find('override fun setupDialog')
if start_idx != -1:
    # Find the preceding annotation
    anno_idx = text.rfind('@SuppressLint', 0, start_idx)
    end_idx = text.find('override fun onViewCreated', start_idx)
    end_idx = text.rfind('@androidx.annotation.OptIn', start_idx, end_idx)
    if end_idx == -1:
        end_idx = text.find('override fun onViewCreated', start_idx)
    text = text[:anno_idx] + text[end_idx:]

text = re.sub(r'override fun onCancel\(dialog: DialogInterface\) \{.*?cleanUp\(\)\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'override fun onDismiss\(dialog: DialogInterface\) \{.*?cleanUp\(\)\n    \}', '', text, flags=re.DOTALL)
text = text.replace('override fun onCreate(', 'override fun onDestroyView() {\n        super.onDestroyView()\n        cleanUp()\n    }\n\n    override fun onCreate(')

# dismiss() and this.dismiss()
text = text.replace('this.dismiss()', '')
text = text.replace('dismiss()', '')

# Replace overlays check for FloatingPlayerService
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

# Add metadata info
text = text.replace('bottomInfo.text = item.author', 'bottomInfo.text = "Author: ${item.author}\\nDuration: ${item.duration}\\nSource: ${item.website}"')

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(text)

