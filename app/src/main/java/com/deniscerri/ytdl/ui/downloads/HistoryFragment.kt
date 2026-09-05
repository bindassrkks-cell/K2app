package com.deniscerri.ytdl.ui.downloads

import android.graphics.BitmapFactory
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.ProgressBar
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.deniscerri.ytdl.R
import com.google.android.material.card.MaterialCardView
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.URL

data class SocialPost(
    val title: String,
    val date: String,
    val thumbnail: String,
    val content: String
)

class HistoryFragment : Fragment() {
    private lateinit var recyclerView: RecyclerView
    private lateinit var progressBar: ProgressBar

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View? {
        val view = inflater.inflate(R.layout.fragment_social_feed, container, false)
        recyclerView = view.findViewById(R.id.social_recycler)
        progressBar = view.findViewById(R.id.social_progress)
        recyclerView.layoutManager = LinearLayoutManager(context)

        loadSocialFeed()
        return view
    }

    private fun loadSocialFeed() {
        progressBar.visibility = View.VISIBLE
        lifecycleScope.launch(Dispatchers.IO) {
            val posts = mutableListOf<SocialPost>()
            try {
                val jsonUrl = "https://raw.githubusercontent.com/Bindassrkks/K2app/main/social.json"
                val text = URL(jsonUrl).readText()
                val array = JSONArray(text)
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    posts.add(
                        SocialPost(
                            title = obj.optString("title", "Islamic Post"),
                            date = obj.optString("date", "Today"),
                            thumbnail = obj.optString("thumbnail", ""),
                            content = obj.optString("content", "")
                        )
                    )
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }

            withContext(Dispatchers.Main) {
                progressBar.visibility = View.GONE
                recyclerView.adapter = SocialFeedAdapter(posts) { post ->
                    showPostDetailsDialog(post)
                }
            }
        }
    }

    private fun showPostDetailsDialog(post: SocialPost) {
        val dialogView = layoutInflater.inflate(R.layout.dialog_social_post_detail, null)
        val img = dialogView.findViewById<ImageView>(R.id.detail_image)
        val title = dialogView.findViewById<TextView>(R.id.detail_title)
        val content = dialogView.findViewById<TextView>(R.id.detail_content)

        title.text = post.title
        content.text = post.content
        if (post.thumbnail.isNotEmpty()) {
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val bmp = BitmapFactory.decodeStream(URL(post.thumbnail).openStream())
                    withContext(Dispatchers.Main) {
                        img.setImageBitmap(bmp)
                        img.visibility = View.VISIBLE
                    }
                } catch (err: Exception) {
                    withContext(Dispatchers.Main) { img.visibility = View.GONE }
                }
            }
        } else {
            img.visibility = View.GONE
        }

        MaterialAlertDialogBuilder(requireContext())
            .setView(dialogView)
            .setPositiveButton("Close", null)
            .show()
    }

    fun openSearchView() {}
}

class SocialFeedAdapter(
    private val list: List<SocialPost>,
    private val onClick: (SocialPost) -> Unit
) : RecyclerView.Adapter<SocialFeedAdapter.ViewHolder>() {

    class ViewHolder(v: View) : RecyclerView.ViewHolder(v) {
        val card: MaterialCardView = v.findViewById(R.id.post_card)
        val thumb: ImageView = v.findViewById(R.id.post_thumb)
        val title: TextView = v.findViewById(R.id.post_title)
        val date: TextView = v.findViewById(R.id.post_date)
        val summary: TextView = v.findViewById(R.id.post_summary)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_social_post, parent, false)
        return ViewHolder(v)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = list[position]
        holder.title.text = item.title
        holder.date.text = item.date
        holder.summary.text = item.content
        if (item.thumbnail.isNotEmpty()) {
            (holder.itemView.context as? androidx.lifecycle.LifecycleOwner)?.lifecycleScope?.launch(Dispatchers.IO) {
                try {
                    val bmp = BitmapFactory.decodeStream(URL(item.thumbnail).openStream())
                    withContext(Dispatchers.Main) {
                        holder.thumb.setImageBitmap(bmp)
                        holder.thumb.visibility = View.VISIBLE
                    }
                } catch (err: Exception) {
                    withContext(Dispatchers.Main) { holder.thumb.visibility = View.GONE }
                }
            }
        } else {
            holder.thumb.visibility = View.GONE
        }
        holder.card.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
