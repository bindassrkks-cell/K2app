import re

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'r') as f:
    kt = f.read()

on_resume_replace = """    override fun onResume() {
        super.onResume()
        if (com.deniscerri.ytdl.service.FloatingPlayerService.instance != null) {
            val service = com.deniscerri.ytdl.service.FloatingPlayerService.instance
            val pos = service?.player?.currentPosition ?: 0L
            requireContext().stopService(android.content.Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java))
            
            // Post delay to ensure player is recreated
            view?.postDelayed({
                videoView.player?.seekTo(pos)
                videoView.player?.play()
            }, 300)
        }
    }

    override fun onDestroyView() {"""

kt = kt.replace('    override fun onDestroyView() {', on_resume_replace)

with open('app/src/main/java/com/deniscerri/ytdl/ui/downloadcard/ResultCardDetailsDialog.kt', 'w') as f:
    f.write(kt)
