import re

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

xml = re.sub(r'(<TextView\s+android:id="@+id/settings".*?/>)', r'\1' + about_xml, xml, flags=re.DOTALL)

with open('app/src/main/res/layout/fragment_more.xml', 'w') as f:
    f.write(xml)

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'r') as f:
    kt = f.read()

kt_imports = """
import android.text.method.LinkMovementMethod
import android.text.Html
"""
kt = re.sub(r'import android.os.Bundle', kt_imports + '\nimport android.os.Bundle', kt)

# Add aboutApp variable
kt = re.sub(r'private lateinit var settings: TextView', r'private lateinit var settings: TextView\n    private lateinit var aboutApp: TextView', kt)
kt = re.sub(r'settings = view.findViewById\(R\.id\.settings\)', r'settings = view.findViewById(R.id.settings)\n        aboutApp = view.findViewById(R.id.about_app)', kt)

about_logic = """
        aboutApp.setOnClickListener {
            showAboutDialog()
        }
"""
kt = re.sub(r'settings\.setOnClickListener \{', about_logic + '\n        settings.setOnClickListener {', kt)

dialog_method = """
    private fun showAboutDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_about_app, null)
        val textAbout = dialogView.findViewById<TextView>(R.id.text_about)
        
        val aboutText = "<b>Kupido player 2 Beta</b><br><br>" +
                "Developed by NoishiXzen, for more tools or apps follow <a href=\\"https://aivorygen.netlify.app\\">aivorygen.netlify.app</a><br><br>" +
                "<b>Github:</b> <a href=\\"https://github.com/pushpajit-dev\\">https://github.com/pushpajit-dev</a><br>" +
                "<b>Discord:</b> NoishiXzen<br>" +
                "<b>Youtube:</b> <a href=\\"https://www.youtube.com/@AivoryGen\\">https://www.youtube.com/@AivoryGen</a><br><br>" +
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

kt = re.sub(r'fun terminateApp\(\) \{', dialog_method + '\n    fun terminateApp() {', kt)

with open('app/src/main/java/com/deniscerri/ytdl/ui/more/MoreFragment.kt', 'w') as f:
    f.write(kt)

