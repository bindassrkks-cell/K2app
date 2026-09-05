import re

with open('app/src/main/java/com/deniscerri/ytdl/OnboardingActivity.kt', 'r') as f:
    text = f.read()

replacement = """        btnNext.setOnClickListener {
            val currentItem = viewPager.currentItem
            if (currentItem == 0) {
                checkboxTc = findViewById(R.id.checkbox_tc)
                if (!checkboxTc.isChecked) {
                    Toast.makeText(this, "Please accept the Terms and Conditions", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
            } else if (currentItem == 1) {
                val spinner = findViewById<Spinner>(R.id.spinner_language)
                if (spinner != null) {
                    val pos = spinner.selectedItemPosition
                    val langCode = when (pos) {
                        0 -> "en"
                        1 -> "bn"
                        2 -> "ta"
                        3 -> "hi"
                        4 -> "es"
                        5 -> "fr"
                        else -> "en"
                    }
                    val appLocale = androidx.core.os.LocaleListCompat.forLanguageTags(langCode)
                    androidx.appcompat.app.AppCompatDelegate.setApplicationLocales(appLocale)
                    prefs.edit().putString("selected_language", langCode).apply()
                }
            }
            if (currentItem < 2) {
                viewPager.currentItem = currentItem + 1
            } else {
                prefs.edit().putBoolean("onboarding_complete", true).apply()
                startActivity(Intent(this, MainActivity::class.java))
                finish()
            }
        }"""

text = re.sub(r'        btnNext\.setOnClickListener \{.*?\}\n        \}', replacement, text, flags=re.DOTALL)

adapter_replacement = """        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            if (position == 1) {
                val spinner = holder.itemView.findViewById<Spinner>(R.id.spinner_language)
                if (spinner != null && spinner.adapter == null) {
                    val languages = arrayOf("English", "Bengali", "Tamil", "Hindi", "Spanish", "French")
                    val adapter = ArrayAdapter(holder.itemView.context, android.R.layout.simple_spinner_dropdown_item, languages)
                    spinner.adapter = adapter
                }
            }
        }"""

text = re.sub(r'        override fun onBindViewHolder\(holder: RecyclerView\.ViewHolder, position: Int\) \{.*?\n        \}', adapter_replacement, text, flags=re.DOTALL)

with open('app/src/main/java/com/deniscerri/ytdl/OnboardingActivity.kt', 'w') as f:
    f.write(text)
