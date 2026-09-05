with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    text = f.read()

target = """        videoView.setFullscreenButtonClickListener { isFullScreen ->
            val listSection = view.findViewById<View>(R.id.list_section)
            val frameLayout = view.findViewById<View>(R.id.frame_layout)
            val params = frameLayout.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
            if (isFullScreen) {
                listSection.visibility = View.GONE
                params.dimensionRatio = null
                params.bottomToBottom = androidx.constraintlayout.widget.ConstraintLayout.LayoutParams.PARENT_ID
            } else {
                listSection.visibility = View.VISIBLE
                params.dimensionRatio = "H,16:9"
                params.bottomToBottom = androidx.constraintlayout.widget.ConstraintLayout.LayoutParams.UNSET
            }
            frameLayout.layoutParams = params
            if (isFullScreen) {
                requireActivity().window?.decorView?.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN
                        or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY)
            } else {
                requireActivity().window?.decorView?.systemUiVisibility = View.SYSTEM_UI_FLAG_VISIBLE
            }
        }"""

replacement = """        videoView.setFullscreenButtonClickListener { isFullScreen ->
            val listSection = view.findViewById<View>(R.id.list_section)
            val frameLayout = view.findViewById<View>(R.id.frame_layout)
            val params = frameLayout.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
            if (isFullScreen) {
                listSection.visibility = View.GONE
                params.dimensionRatio = null
                params.bottomToBottom = androidx.constraintlayout.widget.ConstraintLayout.LayoutParams.PARENT_ID
                requireActivity().requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                requireActivity().window?.decorView?.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN
                        or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY)
            } else {
                listSection.visibility = View.VISIBLE
                params.dimensionRatio = "H,16:9"
                params.bottomToBottom = androidx.constraintlayout.widget.ConstraintLayout.LayoutParams.UNSET
                requireActivity().requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
                requireActivity().window?.decorView?.systemUiVisibility = View.SYSTEM_UI_FLAG_VISIBLE
            }
            frameLayout.layoutParams = params
        }"""

if target in text:
    text = text.replace(target, replacement)
    with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
        f.write(text)
    print("Replaced successfully")
else:
    print("Target not found!")
