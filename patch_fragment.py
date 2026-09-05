import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

# Replace BottomSheetDialogFragment with Fragment
text = text.replace('BottomSheetDialogFragment', 'Fragment')

# Remove onCreateDialog
text = re.sub(r'override fun onCreateDialog\(savedInstanceState: Bundle\?\): Dialog \{.*?return dialog\n    \}', '', text, flags=re.DOTALL)

# Remove setupDialog
text = re.sub(r'@SuppressLint\("RestrictedApi", "SetTextI18n", "UseGetLayoutInflater"\)\n    override fun setupDialog\(dialog: Dialog, style: Int\) \{.*?\}\n', '', text, flags=re.DOTALL)
text = re.sub(r'override fun setupDialog\(dialog: Dialog, style: Int\) \{.*?\}\n', '', text, flags=re.DOTALL)

# Also remove cleanUp call on dismiss because fragment doesn't have onCancel / onDismiss
text = re.sub(r'override fun onCancel\(dialog: DialogInterface\) \{.*?cleanUp\(\)\n    \}', '', text, flags=re.DOTALL)
text = re.sub(r'override fun onDismiss\(dialog: DialogInterface\) \{.*?cleanUp\(\)\n    \}', '', text, flags=re.DOTALL)

# Call cleanup on onDestroyView
text = text.replace('override fun onCreate(', 'override fun onDestroyView() {\n        super.onDestroyView()\n        cleanUp()\n    }\n\n    override fun onCreate(')

# In onCardClick, replace this.dismiss() with findNavController().navigateUp() or nothing (navigate replaces it anyway)
text = text.replace('this.dismiss()', '')

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(text)

