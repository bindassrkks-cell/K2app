import re

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'r') as f:
    kt = f.read()

redirect = """
        val prefs = androidx.preference.PreferenceManager.getDefaultSharedPreferences(this)
        if (!prefs.getBoolean("onboarding_complete", false)) {
            startActivity(android.content.Intent(this, OnboardingActivity::class.java))
            finish()
            return
        }
        super.onCreate(savedInstanceState)
"""

kt = kt.replace('super.onCreate(savedInstanceState)', redirect, 1)

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'w') as f:
    f.write(kt)

