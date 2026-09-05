import re

with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'r') as f:
    content = f.read()

old_share_pending = """                //share intent
                val shareNotificationPendingIntent: PendingIntent = PendingIntent.getActivity(
                    context,
                    id.toInt(),
                    Intent.createChooser(shareFileIntent, res.getString(R.string.share)),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )"""

new_share_pending = """                //share intent
                val chooser = Intent.createChooser(shareFileIntent, res.getString(R.string.share))
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                val shareNotificationPendingIntent: PendingIntent = PendingIntent.getActivity(
                    context,
                    id.toInt(),
                    chooser,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )"""

if old_share_pending in content:
    content = content.replace(old_share_pending, new_share_pending)
    with open('app/src/main/java/com/deniscerri/ytdl/util/NotificationUtil.kt', 'w') as f:
        f.write(content)
    print("Patched NotificationUtil share pending intent")
else:
    print("Could not find share pending intent block in NotificationUtil")

