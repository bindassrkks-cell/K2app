package com.deniscerri.ytdl.ui.more

import android.content.Intent
import android.content.SharedPreferences
import android.os.Build

import android.text.method.LinkMovementMethod
import android.text.Html

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.navigation.fragment.findNavController
import androidx.preference.PreferenceManager
import com.deniscerri.ytdl.MainActivity
import com.deniscerri.ytdl.R
import com.deniscerri.ytdl.database.viewmodel.DownloadViewModel
import com.deniscerri.ytdl.ui.more.settings.SettingsActivity
import com.deniscerri.ytdl.ui.more.terminal.TerminalActivity
import com.deniscerri.ytdl.util.NavbarUtil
import com.google.android.material.color.MaterialColors
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch
import kotlin.system.exitProcess

class MoreFragment : Fragment() {
    private lateinit var mainSharedPreferences: SharedPreferences
    private lateinit var mainSharedPreferencesEditor: SharedPreferences.Editor
    private lateinit var terminal: TextView
    private lateinit var logs: TextView
    private lateinit var commandTemplates: TextView
            private lateinit var cookies: TextView
    private lateinit var observeSources: TextView
    private lateinit var terminateApp: TextView
    private lateinit var settings: TextView
    private lateinit var aboutApp: TextView
    private lateinit var developerMode: TextView
    private lateinit var developerOptionsLayout: View
    private lateinit var mainActivity: MainActivity
    private lateinit var downloadViewModel: DownloadViewModel
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        mainActivity = activity as MainActivity
        downloadViewModel = ViewModelProvider(this)[DownloadViewModel::class.java]
        return inflater.inflate(R.layout.fragment_more, container, false)
    }
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        mainSharedPreferences =  PreferenceManager.getDefaultSharedPreferences(requireContext())
        mainSharedPreferencesEditor = mainSharedPreferences.edit()
        terminal = view.findViewById(R.id.terminal)
        logs = view.findViewById(R.id.logs)
        commandTemplates = view.findViewById(R.id.command_templates)
                        cookies = view.findViewById(R.id.cookies)
        observeSources = view.findViewById(R.id.observe_sources)
        terminateApp = view.findViewById(R.id.terminate)
        settings = view.findViewById(R.id.settings)
        aboutApp = view.findViewById(R.id.about_app)
        developerMode = view.findViewById(R.id.developer_mode)
        developerOptionsLayout = view.findViewById(R.id.developer_options_layout)

        

        var showingTerminal = false
                
        NavbarUtil.getNavBarItems(requireContext()).apply {
            showingTerminal = any { n -> n.itemId == R.id.terminalActivity && n.isVisible }
                                }

        terminal.isVisible = !showingTerminal
                
        developerMode.setOnClickListener {
            developerOptionsLayout.isVisible = !developerOptionsLayout.isVisible
        }

        terminal.setOnClickListener {
            val intent = Intent(context, TerminalActivity::class.java)
            startActivity(intent)
        }

        logs.setOnClickListener {
            findNavController().navigate(R.id.downloadLogListFragment)
        }

        commandTemplates.setOnClickListener {
            findNavController().navigate(R.id.commandTemplatesFragment)
        }

        
        
        cookies.setOnClickListener {
            findNavController().navigate(R.id.cookiesFragment)
        }

        observeSources.setOnClickListener {
            findNavController().navigate(R.id.observeSourcesFragment)
        }

        terminateApp.setOnClickListener {
            showTerminateConfirmationDialog()
        }
        terminateApp.setOnLongClickListener {
            showTerminateConfirmationDialog(skipPreference = true)
            true
        }

        
        aboutApp.setOnClickListener {
            showAboutDialog()
        }

        settings.setOnClickListener {
            val intent = Intent(context, SettingsActivity::class.java)
            startActivity(intent)
        }

    }

    fun showTerminateConfirmationDialog(skipPreference: Boolean = false) {
        val shouldAskToTerminate = mainSharedPreferences.getBoolean("ask_terminate_app", true)
        if (!shouldAskToTerminate && !skipPreference) {
            terminateApp.isEnabled = false
            terminateApp()
            return
        }

        var doNotShowAgainFinalState = !shouldAskToTerminate

        lateinit var dialog: AlertDialog
        val terminateDialog = MaterialAlertDialogBuilder(requireContext())
        terminateDialog.setTitle(getString(R.string.kill_app))
        val dialogView = layoutInflater.inflate(R.layout.dialog_terminate_app, null)
        val checkbox = dialogView.findViewById<CheckBox>(R.id.doNotShowAgain)
        terminateDialog.setView(dialogView)

        checkbox.isChecked = doNotShowAgainFinalState
        checkbox.setOnCheckedChangeListener { _, isChecked ->
            doNotShowAgainFinalState = isChecked
        }

        terminateDialog.setNegativeButton(getString(R.string.cancel)) { dialogInterface, _ ->
            dialogInterface.cancel()
        }

        terminateDialog.setPositiveButton(getString(R.string.ok), null)
        dialog = terminateDialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            dialog.setCanceledOnTouchOutside(false)
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled = false
            dialog.getButton(AlertDialog.BUTTON_NEGATIVE).isEnabled = false
            mainSharedPreferencesEditor.putBoolean("ask_terminate_app", !doNotShowAgainFinalState).commit()
            terminateApp()
        }
    }

    
    private fun showAboutDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_about_app, null)
        val textAbout = dialogView.findViewById<TextView>(R.id.text_about)
        
        val aboutText = "<b>Kupido player 2 Beta</b><br><br>" +
                "Developed by NoishiXzen, for more tools or apps follow <a href=\"https://aivorygen.netlify.app\">aivorygen.netlify.app</a><br><br>" +
                "<b>Github:</b> <a href=\"https://github.com/pushpajit-dev\">https://github.com/pushpajit-dev</a><br>" +
                "<b>Discord:</b> NoishiXzen<br>" +
                "<b>Youtube:</b> <a href=\"https://www.youtube.com/@AivoryGen\">https://www.youtube.com/@AivoryGen</a><br><br>" +
                "<b>Libraries / Components:</b><br>" +
                "• Jetpack Compose &amp; Material 3<br>" +
                "• Media3 (ExoPlayer)<br>" +
                "• Navigation Component<br>" +
                "• Retrofit / OkHttp<br>" +
                "• yt-dlp &amp; FFmpeg (Binary integration)<br>" +
                "• Room Database<br><br>" +
                "<b>General Guide:</b> <a href=\"https://docs.google.com/document/d/1hIThBnHSi44u0Dnklc2ELCb2hUj3dSweCklTlJpMm7E/edit?usp=sharing\">View Guide</a>"
                
        textAbout.text = Html.fromHtml(aboutText, Html.FROM_HTML_MODE_COMPACT)
        textAbout.movementMethod = LinkMovementMethod.getInstance()
        
        MaterialAlertDialogBuilder(requireContext())
            .setView(dialogView)
            .setPositiveButton(getString(R.string.ok), null)
            .show()
    }

    fun terminateApp() {
        lifecycleScope.launch {
            downloadViewModel.pauseAllDownloads()
            mainActivity.finishAndRemoveTask()
            mainActivity.finishAffinity()
            exitProcess(0)
        }
    }

    companion object {
        const val TAG = "MoreFragment"
    }

}