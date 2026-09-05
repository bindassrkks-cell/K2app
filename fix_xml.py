import re

with open('app/src/main/res/layout/result_card_details.xml', 'r') as f:
    content = f.read()

content = re.sub(
    r'<com\.google\.android\.material\.button\.MaterialButton\n\s*<com\.google\.android\.material\.button\.MaterialButton\n\s*android:id="@+id/pip_button"',
    '<com.google.android.material.button.MaterialButton\n            android:id="@+id/pip_button"',
    content
)

with open('app/src/main/res/layout/result_card_details.xml', 'w') as f:
    f.write(content)
