

package com.deniscerri.ytdl.ui.downloadcard
import android.provider.Settings
import android.os.Build

import android.annotation.SuppressLint
import android.app.Dialog
import android.app.DownloadManager
import android.content.Context
import android.content.DialogInterface
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Color
import android.net.Uri

import android.media.AudioManager
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.WindowManager
import kotlin.math.abs

import android.content.Intent

import android.os.Bundle
import android.util.DisplayMetrics
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.ui.PlayerView
import androidx.navigation.fragment.findNavController
import androidx.paging.filter
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.ItemTouchHelper
import androidx.recyclerview.widget.RecyclerView
import androidx.work.WorkManager
import com.deniscerri.ytdl.R
import com.deniscerri.ytdl.database.enums.DownloadType
import com.deniscerri.ytdl.database.models.DownloadItem
import com.deniscerri.ytdl.database.models.ResultItem
import com.deniscerri.ytdl.database.repository.DownloadRepository
import com.deniscerri.ytdl.database.viewmodel.DownloadCardViewModel
import com.deniscerri.ytdl.database.viewmodel.DownloadViewModel
import com.deniscerri.ytdl.database.viewmodel.ResultViewModel
import com.deniscerri.ytdl.database.viewmodel.YTDLPViewModel
import com.deniscerri.ytdl.ui.adapter.ActiveDownloadMinifiedAdapter
import com.deniscerri.ytdl.ui.adapter.GenericDownloadAdapter
import com.deniscerri.ytdl.util.Extensions.setFullScreen
import com.deniscerri.ytdl.util.NotificationUtil
import com.deniscerri.ytdl.util.UiUtil
import com.deniscerri.ytdl.util.VideoPlayerUtil
import com.deniscerri.ytdl.util.WorkerEventBus
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import androidx.fragment.app.Fragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.color.MaterialColors
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.elevation.SurfaceColors
import com.google.android.material.progressindicator.LinearProgressIndicator
import com.google.android.material.snackbar.Snackbar
import it.xabaras.android.recyclerview.swipedecorator.RecyclerViewSwipeDecorator
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext


class ResultCardDetailsDialog : Fragment(), GenericDownloadAdapter.OnItemClickListener, ActiveDownloadMinifiedAdapter.OnItemClickListener {
    private lateinit var notificationUtil: NotificationUtil
    private lateinit var videoView: PlayerView
    private lateinit var downloadViewModel: DownloadViewModel
    private lateinit var resultViewModel: ResultViewModel
    private lateinit var ytdlpViewModel: YTDLPViewModel
    private lateinit var downloadCardViewModel: DownloadCardViewModel

    private lateinit var activeAdapter: ActiveDownloadMinifiedAdapter
    private lateinit var queuedAdapter: GenericDownloadAdapter

    private lateinit var downloadManager: DownloadManager

    private lateinit var sharedPreferences: SharedPreferences
    private lateinit var dialogView : View
    private lateinit var item: ResultItem

    override fun onDestroyView() {
        super.onDestroyView()
        cleanUp()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        notificationUtil = NotificationUtil(requireActivity())
        downloadViewModel = ViewModelProvider(this)[DownloadViewModel::class.java]
        resultViewModel = ViewModelProvider(this)[ResultViewModel::class.java]
        ytdlpViewModel = ViewModelProvider(this)[YTDLPViewModel::class.java]
        downloadCardViewModel = ViewModelProvider(requireActivity())[DownloadCardViewModel::class.java]
        downloadManager = requireContext().getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        sharedPreferences = PreferenceManager.getDefaultSharedPreferences(requireContext())
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        // Inflate the layout to use as dialog or embedded fragment
        dialogView =  inflater.inflate(R.layout.result_card_details, container, false)
        return dialogView
    }
    



    @androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val i = if (Build.VERSION.SDK_INT >= 33){
            arguments?.getParcelable("result", ResultItem::class.java)
        }else{
            arguments?.getParcelable<ResultItem>("result")
        }

        if (i == null) {
            
            return
        }

        item = i

        //remove outdated player url of 1hr so it can refetch it in the player
        if (item.creationTime > System.currentTimeMillis() - 3600000) item.urls = ""

        activeAdapter = ActiveDownloadMinifiedAdapter(this,requireActivity())
        queuedAdapter = GenericDownloadAdapter(this,requireActivity())

        val bottomSheetLink = view.findViewById<MaterialButton>(R.id.bottom_sheet_link)
        val downloadThumb = view.findViewById<MaterialButton>(R.id.download_thumb)

        var streamUrls: List<String>? = null
        val pipButton = view.findViewById<View>(R.id.pip_button)
                pipButton.setOnClickListener {
            if (streamUrls == null) {
                android.widget.Toast.makeText(requireContext(), "Loading video stream, please wait...", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (Build.VERSION.SDK_INT >= 33 && requireContext().checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 101)
                android.widget.Toast.makeText(requireContext(), "Please grant notification permission for background play.", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            if (Settings.canDrawOverlays(requireContext())) {
                val intent = Intent(requireContext(), com.deniscerri.ytdl.service.FloatingPlayerService::class.java)
                intent.putStringArrayListExtra("URLS", ArrayList(streamUrls))
                val currentPos = videoView.player?.currentPosition ?: 0L
                intent.putExtra("POSITION", currentPos)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    requireContext().startForegroundService(intent)
                } else {
                    requireContext().startService(intent)
                }
            } else {
                android.widget.Toast.makeText(requireContext(), "Please grant display over other apps for mini player.", android.widget.Toast.LENGTH_SHORT).show()
                val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, android.net.Uri.parse("package:" + requireContext().packageName))
                startActivity(intent)
            }
        }

        val title = view.findViewById<TextView>(R.id.title)
        val bottomInfo = view.findViewById<TextView>(R.id.bottom_info)
        val downloadMusic = view.findViewById<Button>(R.id.download_music)
        val downloadVideo = view.findViewById<Button>(R.id.download_video)

        val runningRecycler = view.findViewById<RecyclerView>(R.id.running_recycler)
        val running = view.findViewById<TextView>(R.id.running)
        val queuedRecycler = view.findViewById<RecyclerView>(R.id.queued_recycler)
        val queued = view.findViewById<TextView>(R.id.queued)

        runningRecycler.adapter = activeAdapter
        runningRecycler.layoutManager = GridLayoutManager(context, 1)

        val preferences = PreferenceManager.getDefaultSharedPreferences(requireContext())
        if (preferences.getBoolean("swipe_gestures", true)){
            val itemTouchHelper = ItemTouchHelper(simpleCallback)
            itemTouchHelper.attachToRecyclerView(queuedRecycler)
        }

        queuedRecycler.adapter = queuedAdapter
        queuedRecycler.layoutManager = GridLayoutManager(context, resources.getInteger(R.integer.grid_size))

        lifecycleScope.launch {
            downloadViewModel.activeDownloads.map { it.filter { d -> d.url == item.url } }.collectLatest {
                delay(500)
                activeAdapter.submitList(it)
                if (it.isEmpty()){
                    running.visibility = View.GONE
                    runningRecycler.visibility = View.GONE
                }else{
                    running.visibility = View.VISIBLE
                    runningRecycler.visibility = View.VISIBLE
                }
            }
        }

        WorkManager.getInstance(requireContext())
            .getWorkInfosByTagLiveData("download")
            .observe(viewLifecycleOwner){ list ->
                list.forEach {work ->
                    if (work == null) return@forEach
                    val id = work.progress.getLong("id", 0L)
                    if(id == 0L) return@forEach

                    val progress = work.progress.getInt("progress", 0)
                    val progressBar = view.findViewWithTag<LinearProgressIndicator>("$id##progress")
                    requireActivity().runOnUiThread {
                        try {
                            progressBar?.setProgressCompat(progress, true)
                        }catch (ignored: Exception) {}
                    }
                }
            }

        lifecycleScope.launch {
            downloadViewModel.queuedDownloads.map { it.filter { d -> d.url == item.url } }.collectLatest {
                queuedAdapter.submitData(it)
            }
        }

        queuedAdapter.addLoadStateListener { loadState ->
            lifecycleScope.launch {
                if (loadState.append.endOfPaginationReached )
                {
                    if (queuedAdapter.itemCount < 1){
                        queued.visibility = View.GONE
                        queuedRecycler.visibility = View.GONE
                    }else{
                        queued.visibility = View.VISIBLE
                        queuedRecycler.visibility = View.VISIBLE
                    }
                }
            }
        }


        bottomSheetLink.text = item.url
        bottomSheetLink.setOnClickListener{
            UiUtil.openLinkIntent(requireContext(), item.url)
        }
        bottomSheetLink.setOnLongClickListener{
            UiUtil.copyLinkToClipBoard(requireContext(), item.url)
            true
        }

        downloadThumb.isVisible = item.thumb.isNotBlank()
        downloadThumb.setOnClickListener {
            UiUtil.openLinkIntent(requireContext(), item.thumb)
        }

        val shareButton = view.findViewById<View>(R.id.share_button)
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



        title.text = item.title
        bottomInfo.text = "Author: ${item.author}\nDuration: ${item.duration}\nSource: ${item.website}"

        downloadMusic.setOnClickListener {
            onButtonClick(DownloadType.audio)
        }
        downloadMusic.setOnLongClickListener {
            onButtonClick(DownloadType.audio)
            true
        }

        downloadVideo.setOnClickListener {
            onButtonClick(DownloadType.video)
        }
        downloadVideo.setOnLongClickListener {
            onButtonClick(DownloadType.video)
            true
        }


        videoView = view.findViewById(R.id.video_view)
        val player = VideoPlayerUtil.buildPlayer(requireContext())
        videoView.player = player

        videoView.setFullscreenButtonClickListener { isFullScreen ->
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
        }

        
        // Gesture controls for brightness and volume
        val audioManager = requireContext().getSystemService(android.content.Context.AUDIO_SERVICE) as AudioManager
        val gestureDetector = GestureDetector(requireContext(), object : GestureDetector.SimpleOnGestureListener() {
            private var isVolume = false
            private var startY = 0f
            private var startVolume = 0
            private var startBrightness = 0f

            override fun onDown(e: MotionEvent): Boolean {
                val width = videoView.width
                isVolume = e.x > width / 2f
                startY = e.y
                if (isVolume) {
                    startVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
                } else {
                    val window = requireActivity().window
                    startBrightness = window?.attributes?.screenBrightness ?: -1f
                    if (startBrightness < 0) {
                        try {
                            startBrightness = Settings.System.getInt(requireContext().contentResolver, Settings.System.SCREEN_BRIGHTNESS) / 255f
                        } catch (e: Exception) {}
                    }
                }
                return true
            }

            override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
                if (e1 == null) return false
                val deltaY = e1.y - e2.y
                val height = videoView.height
                val percent = deltaY / height

                if (isVolume) {
                    val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                    val change = (percent * maxVolume).toInt()
                    val newVolume = (startVolume + change).coerceIn(0, maxVolume)
                    audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, newVolume, AudioManager.FLAG_SHOW_UI)
                } else {
                    val change = percent
                    val newBrightness = (startBrightness + change).coerceIn(0f, 1f)
                    val window = requireActivity().window
                    val layoutParams = window?.attributes
                    layoutParams?.screenBrightness = newBrightness
                    window?.attributes = layoutParams
                }
                return true
            }
        })

        videoView.setOnTouchListener { _, event ->
            gestureDetector.onTouchEvent(event)
            false
        }

        val loading = view.findViewById<ProgressBar>(R.id.loading)

        lifecycleScope.launch {
            try {
                val data = withContext(Dispatchers.IO) {
                    if (item.urls.isEmpty()) {
                        resultViewModel.getStreamingUrlAndChapters(item.url)
                    }else{
                        Pair(item.urls.split("\n"), null)
                    }
                }

                if (data.first.isEmpty()) throw Exception("No Data found!")
                loading.isVisible = false

                val urls = data.first
                streamUrls = urls
                if (urls.size == 2){
                    val audioSource : MediaSource =
                        DefaultMediaSourceFactory(requireContext())
                            .createMediaSource(MediaItem.fromUri(Uri.parse(urls[0])))
                    val videoSource: MediaSource =
                        DefaultMediaSourceFactory(requireContext())
                            .createMediaSource(MediaItem.fromUri(Uri.parse(urls[1])))
                    player.setMediaSource(MergingMediaSource(videoSource, audioSource))
                }else{
                    player.addMediaItem(MediaItem.fromUri(Uri.parse(urls[0])))
                }

                player.prepare()
                player.play()
            }catch (e: Exception){
                loading.isVisible = false
                e.printStackTrace()
            }
        }

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                WorkerEventBus.events.collectLatest { event ->
                    val progressBar = requireView().findViewWithTag<LinearProgressIndicator>("${event.downloadItemID}##progress")
                    val outputText = requireView().findViewWithTag<TextView>("${event.downloadItemID}##output")

                    requireActivity().runOnUiThread {
                        try {
                            progressBar?.setProgressCompat(event.progress, true)
                            outputText?.text = event.output
                        }catch (ignored: Exception) {}
                    }
                }
            }
        }
    }

    private fun onButtonClick(type: DownloadType){
        if (sharedPreferences.getBoolean("download_card", true)) {
            val bundle = Bundle()
            downloadCardViewModel.setResultItem(item)
            downloadCardViewModel.setDownloadItem(null)
            bundle.putSerializable("type", type)
            findNavController().navigateUp()
            findNavController().navigate(R.id.downloadBottomSheetDialog, bundle)
        } else {
            lifecycleScope.launch{
                val downloadItem = withContext(Dispatchers.IO){
                    downloadViewModel.createDownloadItemFromResult(
                        result = item,
                        givenType = type)
                }
                downloadViewModel.queueDownloads(listOf(downloadItem))
                findNavController().navigateUp()
            }
        }
    }

    

    


    private fun cleanUp(){
        kotlin.runCatching {
            videoView.player?.stop()
            videoView.player?.release()
        }
    }

    private fun removeQueuedItem(id: Long){
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO){
                downloadViewModel.getItemByID(id)
            }
            val deleteDialog = MaterialAlertDialogBuilder(requireContext())
            deleteDialog.setTitle(getString(R.string.you_are_going_to_delete) + " \"" + item.title + "\"!")
            deleteDialog.setNegativeButton(getString(R.string.cancel)) { dialogInterface: DialogInterface, _: Int -> dialogInterface.cancel() }
            deleteDialog.setPositiveButton(getString(R.string.ok)) { _: DialogInterface?, _: Int ->
                item.status = DownloadRepository.Status.Cancelled.toString()
                lifecycleScope.launch(Dispatchers.IO){
                    downloadViewModel.updateDownload(item)
                }

                Snackbar.make(requireView().rootView, getString(R.string.cancelled) + ": " + item.title, Snackbar.LENGTH_LONG)
                    .setAction(getString(R.string.undo)) {
                        lifecycleScope.launch(Dispatchers.IO) {
                            downloadViewModel.deleteDownload(item.id)
                            downloadViewModel.queueDownloads(listOf(item))
                        }
                    }.show()
            }
            deleteDialog.show()
        }
    }

    private var simpleCallback: ItemTouchHelper.SimpleCallback =
        object : ItemTouchHelper.SimpleCallback(0, ItemTouchHelper.LEFT) {
            override fun onMove(recyclerView: RecyclerView, viewHolder: RecyclerView.ViewHolder, target: RecyclerView.ViewHolder
            ): Boolean {
                return false
            }

            override fun onSwiped(viewHolder: RecyclerView.ViewHolder, direction: Int) {
                val itemID = viewHolder.itemView.tag.toString().toLong()
                when (direction) {
                    ItemTouchHelper.LEFT -> {
                        lifecycleScope.launch {
                            val deletedItem = withContext(Dispatchers.IO){
                                downloadViewModel.getItemByID(itemID)
                            }
                            queuedAdapter.notifyItemChanged(viewHolder.bindingAdapterPosition)
                            removeQueuedItem(deletedItem.id)
                        }
                    }

                }
            }

            override fun onChildDraw(
                c: Canvas,
                recyclerView: RecyclerView,
                viewHolder: RecyclerView.ViewHolder,
                dX: Float,
                dY: Float,
                actionState: Int,
                isCurrentlyActive: Boolean
            ) {
                RecyclerViewSwipeDecorator.Builder(
                    requireContext(),
                    c,
                    recyclerView,
                    viewHolder,
                    dX,
                    dY,
                    actionState,
                    isCurrentlyActive
                )
                    .addSwipeLeftBackgroundColor(Color.RED)
                    .addSwipeLeftActionIcon(R.drawable.baseline_delete_24)
                    .addSwipeRightBackgroundColor(
                        MaterialColors.getColor(
                            requireContext(),
                            R.attr.colorOnSurfaceInverse, Color.TRANSPARENT
                        )
                    )
                    .create()
                    .decorate()
                super.onChildDraw(
                    c,
                    recyclerView,
                    viewHolder,
                    dX,
                    dY,
                    actionState,
                    isCurrentlyActive
                )
            }
        }

    override fun onActionButtonClick(itemID: Long) {
        removeQueuedItem(itemID)
    }

    override fun onCardClick(itemID: Long) {
        lifecycleScope.launch {
            val item = withContext(Dispatchers.IO){
                downloadViewModel.getItemByID(itemID)
            }

            UiUtil.showDownloadItemDetailsCard(
                item,
                requireActivity(),
                DownloadRepository.Status.valueOf(item.status),
                ytdlpViewModel,
                sharedPreferences,
                removeItem = { it: DownloadItem, sheet: BottomSheetDialog ->
                    sheet.hide()
                    removeQueuedItem(itemID)
                },
                downloadItem = {
                    runBlocking{
                        downloadViewModel.queueDownloads(listOf(it))
                    }
                },
                longClickDownloadButton = {
                    downloadCardViewModel.setResultItem(downloadViewModel.createResultItemFromDownload(it))
                    downloadCardViewModel.setDownloadItem(it)

                    findNavController().navigate(R.id.downloadBottomSheetDialog, bundleOf(
                        Pair("type", it.type)
                    )
                    )
                },
                scheduleButtonClick = {}
            )
        }
    }

    override fun onCardSelect(isChecked: Boolean, position: Int) {}

    override fun onCancelClick(itemID: Long) {
        lifecycleScope.launch {
            withContext(Dispatchers.IO){
                downloadViewModel.cancelDownload(itemID)
            }
        }
    }

    override fun onPauseClick(itemID: Long, position: Int) {
        lifecycleScope.launch {
            withContext(Dispatchers.IO){
                downloadViewModel.pauseDownload(itemID)
            }
            activeAdapter.notifyItemChanged(position)
        }
    }

    override fun onResumeClick(itemID: Long, position: Int) {
        downloadViewModel.resumeDownload(itemID)
    }

    override fun onCardClick() {
        
        findNavController().navigate(
            R.id.downloadQueueMainFragment
        )
    }
}
