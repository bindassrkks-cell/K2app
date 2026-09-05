import re

with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'r') as f:
    content = f.read()

# Share file intent: add FLAG_ACTIVITY_NEW_TASK to the chooser intent
old_share = """        if (uris.isEmpty()){
            Toast.makeText(context, "Error sharing files!", Toast.LENGTH_SHORT).show()
        }else{
            Intent().apply {
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                action = Intent.ACTION_SEND_MULTIPLE
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
                type = if (uris.size == 1) uris[0].let { context.contentResolver.getType(it) } ?: "media/*" else "*/*"
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            }.run{
                context.startActivity(Intent.createChooser(this, context.getString(R.string.share)))
            }
        }"""

new_share = """        if (uris.isEmpty()){
            Toast.makeText(context, "Error sharing files!", Toast.LENGTH_SHORT).show()
        }else{
            val intent = Intent().apply {
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                action = Intent.ACTION_SEND_MULTIPLE
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
                type = if (uris.size == 1) uris[0].let { context.contentResolver.getType(it) } ?: "media/*" else "*/*"
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
            }
            val chooser = Intent.createChooser(intent, context.getString(R.string.share))
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(chooser)
        }"""

if old_share in content:
    content = content.replace(old_share, new_share)
    with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'w') as f:
        f.write(content)
    print("Patched FileUtil share")
else:
    print("Could not find share block in FileUtil")

