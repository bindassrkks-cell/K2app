package com.deniscerri.ytdl.ui.quran

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.widget.doAfterTextChanged
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.deniscerri.ytdl.R
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.URL

data class Surah(
    val number: Int,
    val name: String,
    val englishName: String,
    val englishTranslation: String,
    val numberOfAyahs: Int,
    val revelationType: String
)

class QuranActivity : AppCompatActivity() {
    private lateinit var recyclerSurahs: RecyclerView
    private lateinit var quranProgress: ProgressBar
    private lateinit var audioPlayerBar: LinearLayout
    private lateinit var btnAudioPlayPause: ImageView
    private lateinit var audioSurahTitle: TextView
    private var mediaPlayer: MediaPlayer? = null
    private val surahList = mutableListOf<Surah>()
    private var adapter: SurahAdapter? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_quran)

        findViewById<View>(R.id.btn_back).setOnClickListener { finish() }
        recyclerSurahs = findViewById(R.id.recycler_surahs)
        quranProgress = findViewById(R.id.quran_progress)
        audioPlayerBar = findViewById(R.id.audio_player_bar)
        btnAudioPlayPause = findViewById(R.id.btn_audio_play_pause)
        audioSurahTitle = findViewById(R.id.audio_surah_title)

        recyclerSurahs.layoutManager = LinearLayoutManager(this)

        findViewById<ImageView>(R.id.btn_audio_close).setOnClickListener {
            stopAudio()
            audioPlayerBar.visibility = View.GONE
        }

        btnAudioPlayPause.setOnClickListener {
            mediaPlayer?.let { player ->
                if (player.isPlaying) {
                    player.pause()
                    btnAudioPlayPause.setImageResource(R.drawable.ic_play)
                } else {
                    player.start()
                    btnAudioPlayPause.setImageResource(R.drawable.ic_pause)
                }
            }
        }

        findViewById<EditText>(R.id.search_surah).doAfterTextChanged { text ->
            val query = text.toString().trim()
            val filtered = if (query.isEmpty()) surahList else surahList.filter {
                it.englishName.contains(query, ignoreCase = true) ||
                it.name.contains(query, ignoreCase = true) ||
                it.number.toString() == query
            }
            adapter?.updateList(filtered)
        }

        loadSurahList()
    }

    private fun loadSurahList() {
        quranProgress.visibility = View.VISIBLE
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val jsonUrl = "https://api.alquran.cloud/v1/surah"
                val text = URL(jsonUrl).readText()
                val json = JSONObject(text)
                val dataArray = json.getJSONArray("data")

                surahList.clear()
                for (i in 0 until dataArray.length()) {
                    val obj = dataArray.getJSONObject(i)
                    surahList.add(
                        Surah(
                            number = obj.getInt("number"),
                            name = obj.getString("name"),
                            englishName = obj.getString("englishName"),
                            englishTranslation = obj.getString("englishNameTranslation"),
                            numberOfAyahs = obj.getInt("numberOfAyahs"),
                            revelationType = obj.getString("revelationType")
                        )
                    )
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }

            withContext(Dispatchers.Main) {
                quranProgress.visibility = View.GONE
                adapter = SurahAdapter(
                    surahList,
                    onSurahClick = { surah -> viewSurahAyahs(surah) },
                    onPlayClick = { surah -> playSurahAudio(surah) }
                )
                recyclerSurahs.adapter = adapter
            }
        }
    }

    private fun playSurahAudio(surah: Surah) {
        audioPlayerBar.visibility = View.VISIBLE
        audioSurahTitle.text = surah.number.toString() + ". " + surah.englishName + " (" + surah.name + ")"
        btnAudioPlayPause.setImageResource(R.drawable.ic_pause)

        stopAudio()
        val audioUrl = String.format("https://server8.mp3quran.net/afs/%03d.mp3", surah.number)
        Toast.makeText(this, "Streaming Surah " + surah.englishName + "...", Toast.LENGTH_SHORT).show()

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                mediaPlayer = MediaPlayer().apply {
                    setAudioAttributes(
                        AudioAttributes.Builder()
                            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .build()
                    )
                    setDataSource(audioUrl)
                    prepare()
                    start()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@QuranActivity, "Audio stream error", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun viewSurahAyahs(surah: Surah) {
        val dialogView = layoutInflater.inflate(R.layout.dialog_quran_surah, null)
        val title = dialogView.findViewById<TextView>(R.id.dialog_surah_title)
        val content = dialogView.findViewById<TextView>(R.id.ayah_content)
        val loading = dialogView.findViewById<ProgressBar>(R.id.ayah_loading)

        title.text = surah.name + " (" + surah.englishName + ") - " + surah.numberOfAyahs + " Ayahs"

        val dialog = MaterialAlertDialogBuilder(this)
            .setView(dialogView)
            .setPositiveButton("Close", null)
            .create()
        dialog.show()

        lifecycleScope.launch(Dispatchers.IO) {
            val sb = StringBuilder()
            try {
                val apiUrl = "https://api.alquran.cloud/v1/surah/" + surah.number + "/editions/quran-uthmani,en.sahih"
                val text = URL(apiUrl).readText()
                val json = JSONObject(text)
                val dataArr = json.getJSONArray("data")
                val arabicAyahs = dataArr.getJSONObject(0).getJSONArray("ayahs")
                val englishAyahs = dataArr.getJSONObject(1).getJSONArray("ayahs")

                for (i in 0 until arabicAyahs.length()) {
                    val arText = arabicAyahs.getJSONObject(i).getString("text")
                    val enText = englishAyahs.getJSONObject(i).getString("text")
                    val num = i + 1
                    sb.append("[" + num + "] " + arText + "\n" + enText + "\n\n")
                }
            } catch (e: Exception) {
                sb.append("Error loading Ayahs: " + e.message)
            }

            withContext(Dispatchers.Main) {
                loading.visibility = View.GONE
                content.text = sb.toString()
            }
        }
    }

    private fun stopAudio() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
    }

    override fun onDestroy() {
        super.onDestroy()
        stopAudio()
    }
}

class SurahAdapter(
    private var list: List<Surah>,
    private val onSurahClick: (Surah) -> Unit,
    private val onPlayClick: (Surah) -> Unit
) : RecyclerView.Adapter<SurahAdapter.ViewHolder>() {

    class ViewHolder(v: View) : RecyclerView.ViewHolder(v) {
        val number: TextView = v.findViewById(R.id.surah_number)
        val english: TextView = v.findViewById(R.id.surah_english_name)
        val meta: TextView = v.findViewById(R.id.surah_meta)
        val arabic: TextView = v.findViewById(R.id.surah_arabic_name)
        val btnPlay: ImageView = v.findViewById(R.id.btn_play_surah)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_surah, parent, false)
        return ViewHolder(v)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = list[position]
        holder.number.text = item.number.toString()
        holder.english.text = item.englishName
        holder.meta.text = item.englishTranslation + " • " + item.numberOfAyahs + " Ayahs • " + item.revelationType
        holder.arabic.text = item.name

        holder.itemView.setOnClickListener { onSurahClick(item) }
        holder.btnPlay.setOnClickListener { onPlayClick(item) }
    }

    override fun getItemCount() = list.size

    fun updateList(newList: List<Surah>) {
        list = newList
        notifyDataSetChanged()
    }
}
