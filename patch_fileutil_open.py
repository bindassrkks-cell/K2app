import re

with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'r') as f:
    content = f.read()

old_open_file = """    fun openFileIntent(context: Context, downloadPath: String) {
        try {
            val uri = FileProvider.getUriForFile(context, context.packageName + ".fileprovider", File(downloadPath))
            println(uri)

            if (uri == null) {
                Toast.makeText(context, "Error opening file!", Toast.LENGTH_SHORT).show()
            } else {
                val ext = downloadPath.substring(downloadPath.lastIndexOf(".") + 1).lowercase()
                val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"

                val intent = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, mime)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

                val chooser = Intent.createChooser(intent, "Open with")
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(chooser)
            }
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(context, "Cannot open file. No application found.", Toast.LENGTH_SHORT).show()
        }
    }"""

new_open_file = """    fun openFileIntent(context: Context, downloadPath: String) {
        try {
            val uri = kotlin.runCatching {
                androidx.documentfile.provider.DocumentFile.fromSingleUri(context, android.net.Uri.parse(downloadPath)).run {
                    if (this?.exists() == true) {
                        this.uri
                    } else if (java.io.File(downloadPath).exists()) {
                        androidx.core.content.FileProvider.getUriForFile(context, context.packageName + ".fileprovider", java.io.File(downloadPath))
                    } else null
                }
            }.getOrNull()

            if (uri == null) {
                android.widget.Toast.makeText(context, "Error opening file!", android.widget.Toast.LENGTH_SHORT).show()
            } else {
                val ext = downloadPath.substring(downloadPath.lastIndexOf(".") + 1).lowercase()
                val mime = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "*/*"

                val intent = Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, mime)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

                val chooser = Intent.createChooser(intent, "Open with")
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(chooser)
            }
        } catch (e: Exception) {
            e.printStackTrace()
            android.widget.Toast.makeText(context, "Cannot open file. No application found.", android.widget.Toast.LENGTH_SHORT).show()
        }
    }"""

if old_open_file in content:
    content = content.replace(old_open_file, new_open_file)
    with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'w') as f:
        f.write(content)
    print("Patched openFileIntent")
else:
    print("Could not find openFileIntent")

