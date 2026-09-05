import re

service_kt = """package com.deniscerri.ytdl.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import android.net.Uri
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.ui.PlayerView
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.deniscerri.ytdl.MainActivity
import com.deniscerri.ytdl.R

class FloatingPlayerService : MediaSessionService() {
    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private var player: ExoPlayer? = null
    private var isCollapsed = false
    private var mediaSession: MediaSession? = null

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        setupFloatingWindow()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val urls = intent?.getStringArrayListExtra("URLS")
        if (urls != null) {
            val position = intent.getLongExtra("POSITION", 0L)
            playVideo(urls, position)
        }
        return START_NOT_STICKY
    }

    private fun setupFloatingWindow() {
        floatingView = LayoutInflater.from(this).inflate(R.layout.layout_floating_player, null)

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

        windowManager.addView(floatingView, params)

        val playerView = floatingView.findViewById<PlayerView>(R.id.floating_video_view)
        val closeBtn = floatingView.findViewById<View>(R.id.floating_close)
        val collapseBtn = floatingView.findViewById<View>(R.id.floating_collapse)
        val logoIcon = floatingView.findViewById<ImageView>(R.id.floating_logo)

        player = ExoPlayer.Builder(this).build()
        val intent = Intent(this, MainActivity::class.java)
        intent.flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        mediaSession = MediaSession.Builder(this, player!!).setSessionActivity(pendingIntent).build()
        
        playerView.player = player

        closeBtn.setOnClickListener {
            if (floatingView.parent != null) {
                windowManager.removeView(floatingView)
            }
        }
        
        collapseBtn.setOnClickListener {
            isCollapsed = true
            playerView.visibility = View.GONE
            closeBtn.visibility = View.GONE
            collapseBtn.visibility = View.GONE
            logoIcon.visibility = View.VISIBLE
            params.width = WindowManager.LayoutParams.WRAP_CONTENT
            params.height = WindowManager.LayoutParams.WRAP_CONTENT
            windowManager.updateViewLayout(floatingView, params)
        }

        logoIcon.setOnClickListener {
            if (isCollapsed) {
                isCollapsed = false
                playerView.visibility = View.VISIBLE
                closeBtn.visibility = View.VISIBLE
                collapseBtn.visibility = View.VISIBLE
                logoIcon.visibility = View.GONE
                params.width = WindowManager.LayoutParams.WRAP_CONTENT
                params.height = WindowManager.LayoutParams.WRAP_CONTENT
                windowManager.updateViewLayout(floatingView, params)
            }
        }

        floatingView.setOnTouchListener(object : View.OnTouchListener {
            private var initialX = 0
            private var initialY = 0
            private var initialTouchX = 0f
            private var initialTouchY = 0f

            override fun onTouch(v: View, event: MotionEvent): Boolean {
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        initialX = params.x
                        initialY = params.y
                        initialTouchX = event.rawX
                        initialTouchY = event.rawY
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        params.x = initialX + (event.rawX - initialTouchX).toInt()
                        params.y = initialY + (event.rawY - initialTouchY).toInt()
                        windowManager.updateViewLayout(floatingView, params)
                        return true
                    }
                }
                return false
            }
        })
    }

    private fun playVideo(urls: List<String>, position: Long) {
        if (urls.size == 2) {
            val audioSource: MediaSource =
                DefaultMediaSourceFactory(this)
                    .createMediaSource(MediaItem.fromUri(Uri.parse(urls[0])))
            val videoSource: MediaSource =
                DefaultMediaSourceFactory(this)
                    .createMediaSource(MediaItem.fromUri(Uri.parse(urls[1])))
            player?.setMediaSource(MergingMediaSource(videoSource, audioSource))
        } else if (urls.isNotEmpty()) {
            player?.addMediaItem(MediaItem.fromUri(Uri.parse(urls[0])))
        }
        if (position > 0L) {
            player?.seekTo(position)
        }
        player?.prepare()
        player?.play()
    }

    override fun onDestroy() {
        mediaSession?.release()
        player?.release()
        if (floatingView.parent != null) {
            windowManager.removeView(floatingView)
        }
        super.onDestroy()
    }
}
"""

with open('app/src/main/java/com/deniscerri/ytdl/service/FloatingPlayerService.kt', 'w') as f:
    f.write(service_kt)
