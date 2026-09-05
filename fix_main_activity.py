import re

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'r') as f:
    text = f.read()

replacement = """    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val prefs = androidx.preference.PreferenceManager.getDefaultSharedPreferences(this)
        if (!prefs.getBoolean("onboarding_complete", false)) {
            startActivity(android.content.Intent(this, OnboardingActivity::class.java))
            finish()
            return
        }"""

text = re.sub(r'    override fun onCreate\(savedInstanceState: Bundle\?\) \{\s*val prefs = androidx\.preference\.PreferenceManager\.getDefaultSharedPreferences\(this\)\s*if \(\!prefs\.getBoolean\("onboarding_complete", false\)\) \{\s*startActivity\(android\.content\.Intent\(this, OnboardingActivity::class\.java\)\)\s*finish\(\)\s*return\s*\}\s*super\.onCreate\(savedInstanceState\)', replacement, text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'w') as f:
    f.write(text)
