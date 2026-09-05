package com.deniscerri.ytdl.service

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.session.CommandButton
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionResult
import androidx.media3.ui.PlayerView
import com.deniscerri.ytdl.MainActivity
import com.deniscerri.ytdl.R
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture

class FloatingPlayerService : MediaSessionService() {

    var player: ExoPlayer? = null
    private var mediaSession: MediaSession? = null

    private var windowManager: WindowManager? = null
    private var floatingView: View? = null
    private var isFloatingViewAdded = false

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    companion object {
        var instance: FloatingPlayerService? = null
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
        setupBackgroundPlayer()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        
        if (intent?.action == "SHOW_MINI_PLAYER") {
            showFloatingPlayer()
            return START_NOT_STICKY
        }
        
        val urls = intent?.getStringArrayListExtra("URLS")
        if (urls != null) {
            val position = intent.getLongExtra("POSITION", 0L)
            playVideo(urls, position)
            // By default, try to show the mini player if we have permission
            showFloatingPlayer()
        }
        return START_NOT_STICKY
    }

    private fun setupBackgroundPlayer() {
        player = ExoPlayer.Builder(this).build()
        val intent = Intent(this, MainActivity::class.java)
        intent.putExtra("RESTORE_PLAYER", true)
        intent.flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)

        val customCommand = SessionCommand("SHOW_MINI_PLAYER", android.os.Bundle.EMPTY)
        val button = CommandButton.Builder()
            .setDisplayName("Mini Player")
            .setIconResId(R.drawable.baseline_restore_page_24)
            .setSessionCommand(customCommand)
            .build()

        mediaSession = MediaSession.Builder(this, player!!)
            .setSessionActivity(pendingIntent)
            .setCustomLayout(listOf(button))
            .setCallback(object : MediaSession.Callback {
                override fun onConnect(
                    session: MediaSession,
                    controller: MediaSession.ControllerInfo
                ): MediaSession.ConnectionResult {
                    val connectionResult = super.onConnect(session, controller)
                    val availableSessionCommands = connectionResult.availableSessionCommands.buildUpon()
                        .add(customCommand)
                        .build()
                    return MediaSession.ConnectionResult.accept(
                        availableSessionCommands,
                        connectionResult.availablePlayerCommands
                    )
                }

                override fun onCustomCommand(
                    session: MediaSession,
                    controller: MediaSession.ControllerInfo,
                    customCommand: SessionCommand,
                    args: android.os.Bundle
                ): ListenableFuture<SessionResult> {
                    if (customCommand.customAction == "SHOW_MINI_PLAYER") {
                        showFloatingPlayer()
                        return Futures.immediateFuture(
                            SessionResult(SessionResult.RESULT_SUCCESS)
                        )
                    }
                    return super.onCustomCommand(session, controller, customCommand, args)
                }
            })
            .build()
    }

    private fun playVideo(urls: List<String>, position: Long) {
        if (urls.size == 2) {
            val audioItem = MediaItem.Builder().setUri(Uri.parse(urls[0])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            val videoItem = MediaItem.Builder().setUri(Uri.parse(urls[1])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            val audioSource: MediaSource =
                DefaultMediaSourceFactory(this).createMediaSource(audioItem)
            val videoSource: MediaSource =
                DefaultMediaSourceFactory(this).createMediaSource(videoItem)
            player?.setMediaSource(MergingMediaSource(videoSource, audioSource))
        } else if (urls.isNotEmpty()) {
            val item = MediaItem.Builder().setUri(Uri.parse(urls[0])).setMediaMetadata(androidx.media3.common.MediaMetadata.Builder().setTitle("Kupido2 Player").build()).build()
            player?.setMediaItem(item)
        }
        if (position > 0L) {
            player?.seekTo(position)
        }
        player?.prepare()
        player?.play()
    }

    fun showFloatingPlayer() {
        if (!Settings.canDrawOverlays(this)) return
        if (isFloatingViewAdded) return

        if (windowManager == null) {
            windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        }
        if (floatingView == null) {
            floatingView = LayoutInflater.from(this).inflate(R.layout.layout_floating_player, null)

            val closeBtn = floatingView?.findViewById<ImageButton>(R.id.floating_close)
            closeBtn?.setOnClickListener {
                stopSelf()
            }

            val collapseBtn = floatingView?.findViewById<ImageButton>(R.id.floating_collapse)
            collapseBtn?.setOnClickListener {
                hideFloatingPlayer()
                // Stays playing in background notification
            }

            val playerView = floatingView?.findViewById<PlayerView>(R.id.floating_video_view)
            playerView?.player = player

            // drag logic
            var initialX = 0
            var initialY = 0
            var initialTouchX = 0f
            var initialTouchY = 0f

            floatingView?.setOnTouchListener { view, event ->
                val layoutParams = view.layoutParams as WindowManager.LayoutParams
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initialX = layoutParams.x
                        initialY = layoutParams.y
                        initialTouchX = event.rawX
                        initialTouchY = event.rawY
                        true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        layoutParams.x = initialX + (event.rawX - initialTouchX).toInt()
                        layoutParams.y = initialY + (event.rawY - initialTouchY).toInt()
                        windowManager?.updateViewLayout(floatingView, layoutParams)
                        true
                    }
                    else -> false
                }
            }
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else
                WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        )
        params.gravity = Gravity.TOP or Gravity.START
        params.x = 0
        params.y = 100

        try {
            windowManager?.addView(floatingView, params)
            isFloatingViewAdded = true
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun hideFloatingPlayer() {
        if (isFloatingViewAdded) {
            windowManager?.removeView(floatingView)
            isFloatingViewAdded = false
        }
    }

    override fun onDestroy() {
        hideFloatingPlayer()
        mediaSession?.release()
        player?.release()
        instance = null
        super.onDestroy()
    }
}
