import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'r') as f:
    content = f.read()

# I need to add back 'downloads' initialization because I didn't actually remove it from the XML if I only replaced a part.
# Wait, I did not put `downloads` back in the `fragment_more.xml`. The user wants 'Downloads' in the Developer Mode? No, "and outside will be Logs, Settings and Developer Modes".
# This means `downloads` doesn't exist anymore!
# So I should remove `downloads.isVisible`, `showingDownloads`, and `downloads.setOnClickListener` from MoreFragment.kt

content = re.sub(r'private lateinit var downloads: TextView\n', '', content)
content = re.sub(r'downloads = view.findViewById\(R.id.downloads\)\n', '', content)
content = re.sub(r'var showingDownloads = false\n', '', content)
content = re.sub(r'showingDownloads = any \{ n -> n\.itemId == R\.id\.historyFragment && n\.isVisible \}\n', '', content)
content = re.sub(r'downloads\.isVisible = !showingDownloads\n', '', content)
content = re.sub(r'downloads\.setOnClickListener \{\n.*?\}\n', '', content, flags=re.DOTALL)

# Let's also remove `downloadQueue` since it wasn't requested, or keep it inside developer mode?
# Actually, let me just add them to XML to avoid compile errors if they were used, OR remove them from Kotlin.
# Let's just remove `downloads` and `downloadQueue` and `commandTemplates` if they are causing errors. Wait, `commandTemplates` IS in the XML!
content = re.sub(r'private lateinit var downloadQueue: TextView\n', '', content)
content = re.sub(r'downloadQueue = view.findViewById\(R.id.download_queue\)\n', '', content)
content = re.sub(r'var showingDownloadQueue = false\n', '', content)
content = re.sub(r'showingDownloadQueue = any \{ n -> n\.itemId == R\.id\.downloadQueueMainFragment && n\.isVisible \}\n', '', content)
content = re.sub(r'downloadQueue\.isVisible = !showingDownloadQueue\n', '', content)
content = re.sub(r'downloadQueue\.setOnClickListener \{\n.*?\}\n', '', content, flags=re.DOTALL)


with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'w') as f:
    f.write(content)
