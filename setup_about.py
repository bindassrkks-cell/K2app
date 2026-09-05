import os
import re

# 1. Ensure dialog_about_app.xml exists (prevents runtime crash)
os.makedirs('app/src/main/res/layout', exist_ok=True)
dialog_layout_path = 'app/src/main/res/layout/dialog_about_app.xml'
if not os.path.exists(dialog_layout_path):
    with open(dialog_layout_path, 'w') as f:
        f.write('''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:padding="20dp">

    <TextView
        android:id="@+id/text_about"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:textSize="14sp"
        android:textColor="?android:attr/textColorPrimary" />
</LinearLayout>''')

# 2. Add 'About App' button to fragment_more.xml
with open('app/src/main/res/layout/fragment_more.xml', 'r') as f:
    xml = f.read()

about_xml = """
            <TextView
                android:id="@+id/about_app"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:drawablePadding="35dp"
                android:textSize="16sp"
                android:paddingVertical="15dp"
                android:text="About App"
                android:textStyle="bold"
                android:clickable="true"
                android:focusable="true"
                android:background="?android:attr/selectableItemBackground"
                android:paddingHorizontal="15dp"
                app:drawableStartCompat="@drawable/ic_info" />
"""

if 'android:id="@+id/about_app"' not in xml:
    xml = re.sub(r'(<TextView\s+android:id="@+id/settings".*?/>)', r'\1' + about_xml, xml, flags=re.DOTALL)
    with open('app/src/main/res/layout/fragment_more.xml', 'w') as f:
        f.write(xml)

# 3. Inject Kotlin logic in MoreFragment.kt
with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'r') as f:
    kt = f.read()

kt_imports = """
import android.text.method.LinkMovementMethod
import android.text.Html
"""
if 'import android.text.Html' not in kt:
    kt = re.sub(r'import android.os.Bundle', kt_imports + '\nimport android.os.Bundle', kt)

# Add aboutApp variable
if 'private lateinit var aboutApp: TextView' not in kt:
    kt = re.sub(
        r'private lateinit var settings: TextView',
        r'private lateinit var settings: TextView\n    private lateinit var aboutApp: TextView',
        kt
    )
    kt = re.sub(
        r'settings = view\.findViewById\(R\.id\.settings\)',
        r'settings = view.findViewById(R.id.settings)\n        aboutApp = view.findViewById(R.id.about_app)',
        kt
    )

about_logic = """
        aboutApp.setOnClickListener {
            showAboutDialog()
        }
"""
if 'showAboutDialog()' not in kt:
    kt = re.sub(r'settings\.setOnClickListener \{', about_logic + '\n        settings.setOnClickListener {', kt)

dialog_method = """
    private fun showAboutDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_about_app, null)
        val textAbout = dialogView.findViewById<TextView>(R.id.text_about)
        
        val aboutText = "<b>Kupido player 2 Beta</b><br><br>" +
                "Developed by <b>Raja_Nisarul</b><br><br>" +
                "<b>Github:</b> <a href=\\"https://github.com/Bindassrkks\\">https://github.com/Bindassrkks</a><br><br>" +
                "<b>Libraries / Components:</b><br>" +
                "• Jetpack Compose &amp; Material 3<br>" +
                "• Media3 (ExoPlayer)<br>" +
                "• Navigation Component<br>" +
                "• Retrofit / OkHttp<br>" +
                "• yt-dlp &amp; FFmpeg (Binary integration)<br>" +
                "• Room Database"
                
        textAbout.text = Html.fromHtml(aboutText, Html.FROM_HTML_MODE_COMPACT)
        textAbout.movementMethod = LinkMovementMethod.getInstance()
        
        MaterialAlertDialogBuilder(requireContext())
            .setView(dialogView)
            .setPositiveButton(getString(R.string.ok), null)
            .show()
    }
"""

if 'fun showAboutDialog()' not in kt:
    kt = kt.replace('fun terminateApp() {', dialog_method + '\n    fun terminateApp() {')

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'w') as f:
    f.write(kt)
