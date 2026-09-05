import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'r') as f:
    content = f.read()

# Add developer_mode variable
content = re.sub(
    r'private lateinit var settings: TextView',
    r'private lateinit var settings: TextView\n    private lateinit var developerMode: TextView\n    private lateinit var developerOptionsLayout: View',
    content
)

# Initialize developerMode and developerOptionsLayout
content = re.sub(
    r'settings = view.findViewById\(R\.id\.settings\)',
    r'settings = view.findViewById(R.id.settings)\n        developerMode = view.findViewById(R.id.developer_mode)\n        developerOptionsLayout = view.findViewById(R.id.developer_options_layout)',
    content
)

# Remove appIcon code
content = re.sub(
    r'val appIcon = view\.findViewById<ImageView>\(R\.id\.app_icon\)[\s\S]*?appIcon\.backgroundTintList = null\n        }',
    r'',
    content
)

# Add listener for developerMode
content = re.sub(
    r'terminal\.setOnClickListener \{',
    r'developerMode.setOnClickListener {\n            developerOptionsLayout.isVisible = !developerOptionsLayout.isVisible\n        }\n\n        terminal.setOnClickListener {',
    content
)

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'w') as f:
    f.write(content)

