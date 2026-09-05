import re

with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'r') as f:
    content = f.read()

old_share = """                    shareFileIntent.apply {
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        action = Intent.ACTION_SEND_MULTIPLE
                        putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
                        type = if (uris.size == 1) uris[0].let { context.contentResolver.getType(it) } ?: "media/*" else "*/*"
                        putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    }"""

new_share = """                    shareFileIntent.apply {
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        if (uris.size == 1) {
                            action = Intent.ACTION_SEND
                            putExtra(Intent.EXTRA_STREAM, uris.first())
                            val ext = filepath.first().substring(filepath.first().lastIndexOf(".") + 1).lowercase()
                            type = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"
                        } else {
                            action = Intent.ACTION_SEND_MULTIPLE
                            putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
                            type = "*/*"
                            putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                        }
                    }"""

if old_share in content:
    content = content.replace(old_share, new_share)
    with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'w') as f:
        f.write(content)
    print("Patched NotificationUtil share intent format")
else:
    print("Could not find share format block in NotificationUtil")

