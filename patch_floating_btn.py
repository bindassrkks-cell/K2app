import re

with open('app/src/main/res/layout/result_card_details.xml', 'r') as f:
    content = f.read()

# Add button
btn_code = """
        <com.google.android.material.button.MaterialButton
            android:id="@+id/pip_button"
            style="@style/Widget.Material3.Button.IconButton"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            app:icon="@drawable/ic_music"
            android:contentDescription="Picture in Picture"
            app:iconSize="30dp"
            app:iconTint="?android:colorAccent"
            app:layout_constraintTop_toTopOf="@+id/frame_layout"
            app:layout_constraintStart_toStartOf="@+id/frame_layout" />
"""

content = re.sub(
    r'<com\.google\.android\.material\.button\.MaterialButton\n\s*android:id="@+id/download_thumb"',
    btn_code.strip() + '\n        <com.google.android.material.button.MaterialButton\n            android:id="@+id/download_thumb"',
    content
)

with open('app/src/main/res/layout/result_card_details.xml', 'w') as f:
    f.write(content)
