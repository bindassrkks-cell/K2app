package com.deniscerri.ytdl

import android.content.Intent
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import com.google.android.material.checkbox.MaterialCheckBox

class OnboardingActivity : AppCompatActivity() {

    private lateinit var viewPager: ViewPager2
    private lateinit var btnNext: Button
    private lateinit var dotsIndicator: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = PreferenceManager.getDefaultSharedPreferences(this)
        if (prefs.getBoolean("onboarding_complete", false)) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_onboarding)

        viewPager = findViewById(R.id.view_pager)
        btnNext = findViewById(R.id.button_next)
        dotsIndicator = findViewById(R.id.dots_indicator)

        viewPager.adapter = OnboardingAdapter()
        viewPager.isUserInputEnabled = false // Prevent swiping to force next button clicks

        viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                if (position == 3) {
                    btnNext.text = "Get Started"
                } else {
                    btnNext.text = "Next"
                }
                updateDots(position)
            }
        })

        setupDots()

        btnNext.setOnClickListener {
            val currentItem = viewPager.currentItem
            if (currentItem == 1) { // Terms page
                val checkboxTc = findViewById<MaterialCheckBox>(R.id.checkbox_tc)
                if (checkboxTc != null && !checkboxTc.isChecked) {
                    Toast.makeText(this, "Please accept the Terms and Conditions", Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }
            } else if (currentItem == 2) { // Language page
                val spinner = findViewById<AutoCompleteTextView>(R.id.spinner_language)
                if (spinner != null) {
                    val langStr = spinner.text.toString()
                    val langCode = when (langStr) {
                        "English" -> "en"
                        "Bengali" -> "bn"
                        "Tamil" -> "ta"
                        "Hindi" -> "hi"
                        "Spanish" -> "es"
                        "French" -> "fr"
                        else -> "en"
                    }
                    val appLocale = androidx.core.os.LocaleListCompat.forLanguageTags(langCode)
                    androidx.appcompat.app.AppCompatDelegate.setApplicationLocales(appLocale)
                    prefs.edit().putString("selected_language", langCode).apply()
                }
            }

            if (currentItem < 3) {
                viewPager.setCurrentItem(currentItem + 1, true)
            } else {
                prefs.edit().putBoolean("onboarding_complete", true).apply()
                startActivity(Intent(this, MainActivity::class.java))
                finish()
            }
        }
    }

    private fun setupDots() {
        val count = viewPager.adapter?.itemCount ?: 0
        dotsIndicator.removeAllViews()
        for (i in 0 until count) {
            val dot = View(this)
            val params = LinearLayout.LayoutParams(24, 24)
            params.setMargins(12, 0, 12, 0)
            dot.layoutParams = params
            dot.setBackgroundResource(R.drawable.circle)
            dot.alpha = if (i == 0) 1f else 0.3f
            dotsIndicator.addView(dot)
        }
    }

    private fun updateDots(position: Int) {
        val count = dotsIndicator.childCount
        for (i in 0 until count) {
            dotsIndicator.getChildAt(i).alpha = if (i == position) 1f else 0.3f
        }
    }

    inner class OnboardingAdapter : RecyclerView.Adapter<RecyclerView.ViewHolder>() {
        override fun getItemViewType(position: Int): Int = position

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
            val layout = when (viewType) {
                0 -> R.layout.page_onboarding_welcome
                1 -> R.layout.page_onboarding_terms
                2 -> R.layout.page_onboarding_language
                else -> R.layout.page_onboarding_finish
            }
            val view = LayoutInflater.from(parent.context).inflate(layout, parent, false)
            return object : RecyclerView.ViewHolder(view) {}
        }

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            if (position == 2) {
                val spinner = holder.itemView.findViewById<AutoCompleteTextView>(R.id.spinner_language)
                if (spinner != null && spinner.adapter == null) {
                    val languages = arrayOf("English", "Bengali", "Tamil", "Hindi", "Spanish", "French")
                    val adapter = ArrayAdapter(holder.itemView.context, android.R.layout.simple_list_item_1, languages)
                    spinner.setAdapter(adapter)
                    // Set default value without triggering dropdown
                    spinner.setText("English", false)
                }
            }
        }

        override fun getItemCount(): Int = 4
    }
}
