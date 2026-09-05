import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    content = f.read()

# Replace setFullscreenButtonClickListener
old_fullscreen = """        videoView.setFullscreenButtonClickListener { isFullScreen ->
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

new_fullscreen = """        videoView.setFullscreenButtonClickListener { isFullScreen ->
            val listSectionScroll = view.findViewById<View>(R.id.list_section_scroll)
            val frameLayout = view.findViewById<View>(R.id.frame_layout)
            
            val params = frameLayout.layoutParams as android.widget.LinearLayout.LayoutParams
            val videoViewChild = view.findViewById<View>(R.id.video_view)
            val videoParams = videoViewChild.layoutParams as androidx.constraintlayout.widget.ConstraintLayout.LayoutParams
            
            if (isFullScreen) {
                listSectionScroll.visibility = View.GONE
                params.height = 0
                params.weight = 1f
                videoParams.dimensionRatio = null
                videoViewChild.layoutParams = videoParams
                
                requireActivity().requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                requireActivity().window?.decorView?.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN
                        or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY)
            } else {
                listSectionScroll.visibility = View.VISIBLE
                params.height = android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
                params.weight = 0f
                videoParams.dimensionRatio = "H,16:9"
                videoViewChild.layoutParams = videoParams
                
                requireActivity().requestedOrientation = android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
                requireActivity().window?.decorView?.systemUiVisibility = View.SYSTEM_UI_FLAG_VISIBLE
            }
            frameLayout.layoutParams = params
        }"""

if old_fullscreen in content:
    content = content.replace(old_fullscreen, new_fullscreen)
else:
    print("Could not find old_fullscreen block")

# Add share and open buttons logic
share_logic = """        val shareButton = view.findViewById<View>(R.id.share_button)
        shareButton.setOnClickListener {
            val sendIntent: Intent = Intent().apply {
                action = Intent.ACTION_SEND
                putExtra(Intent.EXTRA_TEXT, item.url)
                type = "text/plain"
            }
            val shareIntent = Intent.createChooser(sendIntent, null)
            startActivity(shareIntent)
        }

        val openButton = view.findViewById<View>(R.id.open_button)
        openButton.setOnClickListener {
            val videoUrl = if (streamUrls != null && streamUrls!!.isNotEmpty()) streamUrls!![0] else item.url
            val intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(android.net.Uri.parse(videoUrl), "video/*")
            startActivity(Intent.createChooser(intent, "Open Video"))
        }

"""

old_download_thumb = """        downloadThumb.isVisible = item.thumb.isNotBlank()
        downloadThumb.setOnClickListener {
            UiUtil.openLinkIntent(requireContext(), item.thumb)
        }"""

new_download_thumb = old_download_thumb + "\n\n" + share_logic

if old_download_thumb in content:
    content = content.replace(old_download_thumb, new_download_thumb)
else:
    print("Could not find old_download_thumb block")

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(content)

