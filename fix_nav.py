import re

with open('app/src/main/res/navigation/nav_graph.xml', 'r') as f:
    content = f.read()

fragments = [
    "homeFragment",
    "historyFragment",
    "moreFragment",
    "cookiesFragment",
    "commandTemplatesFragment",
    "downloadQueueMainFragment",
    "downloadLogListFragment",
    "downloadLogFragment",
    "folderSettingsFragment",
    "processingSettingsFragment",
    "downloadSettingsFragment",
    "updateSettingsFragment",
    "mainSettingsFragment",
    "appearanceSettingsFragment",
    "observeSourcesFragment"
]

for frag in fragments:
    # simply find '<dialog\n        android:id="@+id/homeFragment"'
    content = content.replace(f'<dialog\n        android:id="@+id/{frag}"', f'<fragment\n        android:id="@+id/{frag}"')
    content = content.replace(f'<dialog\n            android:id="@+id/{frag}"', f'<fragment\n            android:id="@+id/{frag}"')

lines = content.split('\n')
stack = []
out_lines = []
for line in lines:
    if '<fragment' in line and '/>' not in line:
        stack.append('fragment')
    elif '<dialog' in line and '/>' not in line:
        stack.append('dialog')
    elif '<activity' in line and '/>' not in line:
        stack.append('activity')
    elif '<navigation' in line and '/>' not in line:
        stack.append('navigation')
    elif re.search(r'</(fragment|dialog|activity|navigation)>', line):
        top = stack.pop()
        line = re.sub(r'</(fragment|dialog|activity|navigation)>', f'</{top}>', line)
    
    out_lines.append(line)

with open('app/src/main/res/navigation/nav_graph.xml', 'w') as f:
    f.write('\n'.join(out_lines))

