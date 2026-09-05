import re

with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'r') as f:
    text = f.read()

replacement = """    fun openFileIntent(context: Context, downloadPath: String) {
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

text = re.sub(r'    fun openFileIntent\(context: Context, downloadPath: String\).*?context\.startActivity\(intent\)\n        }\n\n    }', replacement, text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/util/FileUtil.kt', 'w') as f:
    f.write(text)
