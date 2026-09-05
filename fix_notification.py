import re

with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'r') as f:
    content = f.read()

old_open = """                    openFileIntent.apply {
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        action = Intent.ACTION_VIEW
                        data = uris.first()
                    }"""

new_open = """                    openFileIntent.apply {
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        action = Intent.ACTION_VIEW
                        val fileUri = uris.first()
                        val ext = filepath.first().substring(filepath.first().lastIndexOf(".") + 1).lowercase()
                        val mime = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"
                        setDataAndType(fileUri, mime)
                    }"""

if old_open in content:
    content = content.replace(old_open, new_open)
    with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'w') as f:
        f.write(content)
    print("Patched NotificationUtil")
else:
    print("Could not find open block in NotificationUtil")

