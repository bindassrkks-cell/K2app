import re

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'r') as f:
    kt = f.read()

handle_intents_replace = """    private fun handleIntents(intent: Intent) {
        if (intent.getBooleanExtra("RESTORE_PLAYER", false)) {
            val navHostFragment = supportFragmentManager.findFragmentById(R.id.nav_host_fragment) as androidx.navigation.fragment.NavHostFragment
            val navController = navHostFragment.navController
            if (navController.currentDestination?.id != R.id.resultCardDetailsDialog) {
                try {
                    navController.navigate(R.id.resultCardDetailsDialog)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
            return
        }
        val action = intent.action"""

kt = kt.replace('    private fun handleIntents(intent: Intent) {\n        val action = intent.action', handle_intents_replace)

with open('app/src/main/java/com/deniscerri/ytdl/MainActivity.kt', 'w') as f:
    f.write(kt)
