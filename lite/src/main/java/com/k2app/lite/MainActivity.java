package com.k2app.lite;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;
import com.google.android.material.switchmaterial.SwitchMaterial;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends AppCompatActivity {
    private static final int MENU_HOME = 1;
    private static final int MENU_DOWNLOADS = 2;
    private static final int MENU_SETTINGS = 3;
    private static final String PREFS = "k2_lite_preferences";
    private static final String JOBS_KEY = "jobs_v1";
    private static final String WIFI_ONLY_KEY = "wifi_only";
    private static final String QUALITY_KEY = "default_quality";

    private static final int BG = Color.rgb(16, 20, 17);
    private static final int SURFACE = Color.rgb(27, 33, 30);
    private static final int SURFACE_2 = Color.rgb(36, 43, 39);
    private static final int LIME = Color.rgb(184, 243, 90);
    private static final int TEXT = Color.rgb(243, 245, 242);
    private static final int MUTED = Color.rgb(161, 170, 163);
    private static final int OUTLINE = Color.rgb(57, 67, 61);
    private static final int INK = Color.rgb(17, 23, 13);
    private static final int ERROR = Color.rgb(255, 180, 171);

    private enum Section { HOME, DOWNLOADS, SETTINGS }

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final List<DownloadRecord> jobs = new ArrayList<>();
    private Section section = Section.HOME;
    private boolean showingOptions;
    private boolean completedTab;
    private int selectedChoice = -1;
    private String selectedKind = "video";
    private String pendingUrl = "";
    private String homeMessage = "";
    private String pairingMessage = "";
    private String botUrl = "https://t.me/x_amtop_bot";
    private String botUsername = "x_amtop_bot";
    private JSONObject pendingJob;
    private JSONArray pendingChoices;
    private TextInputEditText urlInput;
    private TextInputEditText pairingInput;
    private FrameLayout contentFrame;
    private BottomNavigationView bottomNavigation;
    private LiteApi api;
    private TokenStore tokenStore;
    private SharedPreferences preferences;
    private boolean pollInFlight;
    private boolean activityResumed;

    private final Runnable pollRunnable = this::pollActiveJobs;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(0);

        api = new LiteApi(BuildConfig.LITE_API_BASE_URL);
        tokenStore = new TokenStore(this);
        preferences = getSharedPreferences(PREFS, MODE_PRIVATE);
        loadJobs();

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        contentFrame = new FrameLayout(this);
        root.addView(contentFrame, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        bottomNavigation = createBottomNavigation();
        root.addView(bottomNavigation, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(76)));
        setContentView(root);

        bottomNavigation.setOnItemSelectedListener(item -> {
            if (item.getItemId() == MENU_HOME) section = Section.HOME;
            else if (item.getItemId() == MENU_DOWNLOADS) section = Section.DOWNLOADS;
            else if (item.getItemId() == MENU_SETTINGS) section = Section.SETTINGS;
            showingOptions = false;
            render();
            return true;
        });

        String sharedText = getSharedMediaText(getIntent());
        if (!TextUtils.isEmpty(sharedText)) pendingUrl = sharedText;
        render();
        fetchServiceIdentity();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String sharedText = getSharedMediaText(intent);
        if (!TextUtils.isEmpty(sharedText)) {
            pendingUrl = sharedText;
            section = Section.HOME;
            showingOptions = false;
            render();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        activityResumed = true;
        schedulePoll(2_000);
    }

    @Override
    protected void onPause() {
        activityResumed = false;
        handler.removeCallbacks(pollRunnable);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        io.shutdownNow();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (showingOptions) {
            showingOptions = false;
            section = Section.HOME;
            render();
            return;
        }
        if (section != Section.HOME) {
            section = Section.HOME;
            completedTab = false;
            render();
            return;
        }
        super.onBackPressed();
    }

    private BottomNavigationView createBottomNavigation() {
        BottomNavigationView navigation = new BottomNavigationView(this);
        navigation.setBackgroundColor(SURFACE);
        navigation.setLabelVisibilityMode(BottomNavigationView.LABEL_VISIBILITY_LABELED);
        navigation.setItemIconTintList(new ColorStateList(
                new int[][] { new int[] { android.R.attr.state_checked }, new int[] {} },
                new int[] { LIME, MUTED }));
        navigation.setItemTextColor(new ColorStateList(
                new int[][] { new int[] { android.R.attr.state_checked }, new int[] {} },
                new int[] { LIME, MUTED }));
        navigation.getMenu().add(0, MENU_HOME, 0, "Home").setIcon(R.drawable.ic_nav_home);
        navigation.getMenu().add(0, MENU_DOWNLOADS, 1, "Downloads").setIcon(R.drawable.ic_nav_download);
        navigation.getMenu().add(0, MENU_SETTINGS, 2, "Settings").setIcon(R.drawable.ic_nav_settings);
        return navigation;
    }

    private void render() {
        if (contentFrame == null) return;
        bottomNavigation.setVisibility(showingOptions ? View.GONE : View.VISIBLE);
        if (!showingOptions) {
            int selectedId = section == Section.HOME ? MENU_HOME
                    : section == Section.DOWNLOADS ? MENU_DOWNLOADS : MENU_SETTINGS;
            if (bottomNavigation.getSelectedItemId() != selectedId) {
                bottomNavigation.setOnItemSelectedListener(null);
                bottomNavigation.setSelectedItemId(selectedId);
                bottomNavigation.setOnItemSelectedListener(item -> {
                    if (item.getItemId() == MENU_HOME) section = Section.HOME;
                    else if (item.getItemId() == MENU_DOWNLOADS) section = Section.DOWNLOADS;
                    else if (item.getItemId() == MENU_SETTINGS) section = Section.SETTINGS;
                    showingOptions = false;
                    render();
                    return true;
                });
            }
        }
        contentFrame.removeAllViews();
        View page = showingOptions ? makeOptionsPage()
                : section == Section.HOME ? makeHomePage()
                : section == Section.DOWNLOADS ? makeDownloadsPage()
                : makeSettingsPage();
        contentFrame.addView(page, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private ScrollView newScrollPage() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        scroll.setBackgroundColor(BG);
        scroll.setPadding(dp(20), dp(12), dp(20), dp(24));
        return scroll;
    }

    private LinearLayout newColumn() {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setClipToPadding(false);
        return column;
    }

    private LinearLayout newRow() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        return row;
    }

    private View makeHomePage() {
        ScrollView scroll = newScrollPage();
        LinearLayout column = newColumn();
        scroll.addView(column);

        column.addView(brandHeader(), matchWrap());
        addSpace(column, 22);

        MaterialCardView entryCard = card();
        LinearLayout entry = paddedColumn(20);
        entryCard.addView(entry);
        entry.addView(label("Paste a link", 23, TEXT, true));
        addSpace(entry, 14);
        TextInputLayout inputLayout = new TextInputLayout(this);
        inputLayout.setHint("Video or audio link");
        inputLayout.setBoxBackgroundMode(TextInputLayout.BOX_BACKGROUND_OUTLINE);
        inputLayout.setBoxStrokeColor(OUTLINE);
        inputLayout.setHintTextColor(ColorStateList.valueOf(MUTED));
        inputLayout.setBoxCornerRadii(dp(18), dp(18), dp(18), dp(18));
        urlInput = new TextInputEditText(inputLayout.getContext());
        urlInput.setSingleLine(true);
        urlInput.setTextColor(TEXT);
        urlInput.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        urlInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        urlInput.setText(pendingUrl);
        inputLayout.addView(urlInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        entry.addView(inputLayout, matchWrap());
        addSpace(entry, 14);
        MaterialButton analyze = primaryButton("Analyze link");
        analyze.setOnClickListener(v -> analyzeLink(urlInput == null ? "" : String.valueOf(urlInput.getText())));
        entry.addView(analyze, matchWrap());
        addSpace(entry, 10);
        TextView paste = label("▣   Link copied? Paste it here", 14, MUTED, false);
        paste.setPadding(dp(8), dp(10), dp(8), dp(8));
        paste.setOnClickListener(v -> pasteFromClipboard());
        entry.addView(paste, matchWrap());
        if (!TextUtils.isEmpty(homeMessage)) {
            addSpace(entry, 4);
            entry.addView(label(homeMessage, 13, ERROR, false), matchWrap());
        }
        column.addView(entryCard, matchWrap());

        addSpace(column, 22);
        column.addView(sectionHeading("Recent"), matchWrap());
        addSpace(column, 10);
        if (jobs.isEmpty()) {
            MaterialCardView empty = card();
            LinearLayout emptyContent = paddedColumn(18);
            empty.addView(emptyContent);
            emptyContent.addView(label("Your downloads appear here", 16, TEXT, true));
            addSpace(emptyContent, 5);
            emptyContent.addView(label("Analyze a public video or audio link to get started.", 14, MUTED, false));
            column.addView(empty, matchWrap());
        } else {
            List<DownloadRecord> recent = sortedJobs();
            for (int i = 0; i < Math.min(3, recent.size()); i++) {
                DownloadRecord record = recent.get(i);
                column.addView(makeRecentCard(record), matchWrap());
                addSpace(column, 9);
            }
        }
        return scroll;
    }

    private View brandHeader() {
        LinearLayout row = newRow();
        TextView emblem = label("↗", 26, LIME, true);
        emblem.setGravity(Gravity.CENTER);
        GradientDrawable iconBackground = rounded(SURFACE_2, 18);
        emblem.setBackground(iconBackground);
        row.addView(emblem, new LinearLayout.LayoutParams(dp(48), dp(48)));
        addSpaceHorizontal(row, 12);
        LinearLayout titleStack = newColumn();
        TextView title = label("K2 LITE", 24, TEXT, true);
        title.setLetterSpacing(0.05f);
        titleStack.addView(title, matchWrap());
        titleStack.addView(label("Fast downloads. Simple.", 14, MUTED, false), matchWrap());
        row.addView(titleStack, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return row;
    }

    private View makeRecentCard(DownloadRecord record) {
        MaterialCardView card = card();
        LinearLayout row = newRow();
        row.setPadding(dp(14), dp(14), dp(14), dp(14));
        TextView badge = label(record.isCompleted() ? "✓" : "↓", 19, INK, true);
        badge.setGravity(Gravity.CENTER);
        badge.setBackground(rounded(LIME, 24));
        row.addView(badge, new LinearLayout.LayoutParams(dp(42), dp(42)));
        addSpaceHorizontal(row, 12);
        LinearLayout detail = newColumn();
        detail.addView(label(record.title, 16, TEXT, true), matchWrap());
        addSpace(detail, 4);
        detail.addView(label(record.isCompleted() ? "Ready in Telegram" : friendlyStatus(record), 13,
                record.isCompleted() ? LIME : MUTED, false), matchWrap());
        row.addView(detail, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        card.addView(row);
        card.setOnClickListener(v -> {
            section = Section.DOWNLOADS;
            completedTab = record.isCompleted();
            render();
        });
        return card;
    }

    private View makeOptionsPage() {
        ScrollView scroll = newScrollPage();
        LinearLayout column = newColumn();
        scroll.addView(column);

        LinearLayout top = newRow();
        TextView back = label("‹", 34, TEXT, false);
        back.setGravity(Gravity.CENTER);
        top.addView(back, new LinearLayout.LayoutParams(dp(42), dp(44)));
        back.setOnClickListener(v -> {
            showingOptions = false;
            section = Section.HOME;
            render();
        });
        addSpaceHorizontal(top, 10);
        top.addView(label("Download options", 22, TEXT, true), matchWrap());
        column.addView(top, matchWrap());
        addSpace(column, 14);

        JSONObject media = pendingJob == null ? new JSONObject() : pendingJob.optJSONObject("media");
        String title = media == null ? "Media" : media.optString("title", "Media");
        String thumb = media == null ? "" : media.optString("thumbnail_url", "");
        MaterialCardView mediaCard = card();
        LinearLayout mediaRow = newRow();
        mediaRow.setPadding(dp(12), dp(12), dp(12), dp(12));
        ImageView thumbnail = new ImageView(this);
        thumbnail.setBackground(rounded(SURFACE_2, 14));
        thumbnail.setScaleType(ImageView.ScaleType.CENTER_CROP);
        thumbnail.setImageResource(R.drawable.ic_k2_lite);
        mediaRow.addView(thumbnail, new LinearLayout.LayoutParams(dp(122), dp(86)));
        loadThumbnail(thumb, thumbnail);
        addSpaceHorizontal(mediaRow, 12);
        LinearLayout mediaDetails = newColumn();
        mediaDetails.addView(label(title, 17, TEXT, true), matchWrap());
        addSpace(mediaDetails, 4);
        mediaDetails.addView(label(shortUrl(pendingUrl), 13, MUTED, false), matchWrap());
        mediaRow.addView(mediaDetails, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        mediaCard.addView(mediaRow);
        column.addView(mediaCard, matchWrap());
        addSpace(column, 18);

        column.addView(label("Format", 16, MUTED, true), matchWrap());
        addSpace(column, 8);
        LinearLayout filters = newRow();
        addFilter(filters, "Video", "video");
        addFilter(filters, "Audio", "audio");
        if (hasChoiceKind("thumbnail")) addFilter(filters, "Other", "thumbnail");
        column.addView(filters, matchWrap());
        addSpace(column, 16);
        column.addView(label(selectedKind.equals("audio") ? "Quality" : "Available quality", 16, MUTED, true), matchWrap());
        addSpace(column, 8);

        int visibleChoices = 0;
        if (pendingChoices != null) {
            for (int i = 0; i < pendingChoices.length(); i++) {
                JSONObject choice = pendingChoices.optJSONObject(i);
                if (choice == null || !selectedKind.equals(choice.optString("kind", "video"))) continue;
                visibleChoices++;
                column.addView(makeChoiceCard(i, choice), matchWrap());
                addSpace(column, 9);
            }
        }
        if (visibleChoices == 0) {
            column.addView(label("No options of this type are available for this link.", 14, MUTED, false), matchWrap());
        }
        addSpace(column, 8);
        column.addView(label("Files are delivered to your paired Telegram chat.", 13, MUTED, false), matchWrap());
        addSpace(column, 14);
        MaterialButton start = primaryButton("↓   Start download");
        start.setOnClickListener(v -> startSelectedDownload());
        column.addView(start, matchWrap());
        addSpace(column, 12);
        return scroll;
    }

    private void addFilter(LinearLayout parent, String caption, String kind) {
        TextView chip = label(caption, 14, selectedKind.equals(kind) ? INK : MUTED, true);
        chip.setGravity(Gravity.CENTER);
        chip.setPadding(dp(20), dp(10), dp(20), dp(10));
        chip.setBackground(rounded(selectedKind.equals(kind) ? LIME : SURFACE_2, 24));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.rightMargin = dp(8);
        parent.addView(chip, params);
        chip.setOnClickListener(v -> {
            selectedKind = kind;
            selectedChoice = firstChoiceOfKind(kind);
            render();
        });
    }

    private View makeChoiceCard(int index, JSONObject choice) {
        boolean selected = index == selectedChoice;
        MaterialCardView choiceCard = card();
        choiceCard.setStrokeColor(selected ? LIME : OUTLINE);
        choiceCard.setStrokeWidth(dp(selected ? 2 : 1));
        LinearLayout row = newRow();
        row.setPadding(dp(15), dp(15), dp(15), dp(15));
        TextView radio = label(selected ? "◉" : "◯", 22, selected ? LIME : MUTED, false);
        row.addView(radio, new LinearLayout.LayoutParams(dp(32), ViewGroup.LayoutParams.WRAP_CONTENT));
        addSpaceHorizontal(row, 8);
        LinearLayout detail = newColumn();
        String choiceLabel = choice.optString("label", "Media");
        detail.addView(label(choiceLabel, 16, TEXT, true), matchWrap());
        String sub = "thumbnail".equals(choice.optString("kind"))
                ? "Image" : choice.optString("kind", "video").equals("audio") ? "MP3 audio" : videoDetail(choice);
        addSpace(detail, 4);
        detail.addView(label(sub, 13, MUTED, false), matchWrap());
        row.addView(detail, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (isRecommended(choice)) {
            TextView recommended = label("Recommended", 11, INK, true);
            recommended.setGravity(Gravity.CENTER);
            recommended.setPadding(dp(9), dp(6), dp(9), dp(6));
            recommended.setBackground(rounded(LIME, 20));
            row.addView(recommended, wrap());
        }
        choiceCard.addView(row);
        choiceCard.setOnClickListener(v -> {
            selectedChoice = index;
            render();
        });
        return choiceCard;
    }

    private View makeDownloadsPage() {
        ScrollView scroll = newScrollPage();
        LinearLayout column = newColumn();
        scroll.addView(column);
        column.addView(brandHeader(), matchWrap());
        addSpace(column, 18);
        LinearLayout heading = newRow();
        heading.addView(label("Downloads", 28, TEXT, true), new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        MaterialButton clear = smallTextButton("Clear finished", false);
        clear.setOnClickListener(v -> clearFinished());
        heading.addView(clear, wrap());
        column.addView(heading, matchWrap());
        addSpace(column, 14);

        LinearLayout tabs = newRow();
        MaterialButton active = smallTextButton("Active", !completedTab);
        MaterialButton completed = smallTextButton("Completed", completedTab);
        tabs.addView(active, new LinearLayout.LayoutParams(0, dp(44), 1f));
        addSpaceHorizontal(tabs, 8);
        tabs.addView(completed, new LinearLayout.LayoutParams(0, dp(44), 1f));
        active.setOnClickListener(v -> { completedTab = false; render(); });
        completed.setOnClickListener(v -> { completedTab = true; render(); });
        column.addView(tabs, matchWrap());
        addSpace(column, 12);

        List<DownloadRecord> sorted = sortedJobs();
        int count = 0;
        for (DownloadRecord record : sorted) {
            if (record.isCompleted() != completedTab) continue;
            count++;
            column.addView(makeJobCard(record), matchWrap());
            addSpace(column, 10);
        }
        if (count == 0) {
            MaterialCardView emptyCard = card();
            LinearLayout empty = paddedColumn(18);
            emptyCard.addView(empty);
            empty.addView(label(completedTab ? "Nothing completed yet" : "No active downloads", 17, TEXT, true), matchWrap());
            addSpace(empty, 5);
            empty.addView(label(completedTab
                    ? "Finished transfers will appear here. Your files are delivered by the Telegram bot."
                    : "Paste a link on Home to start a transfer.", 14, MUTED, false), matchWrap());
            column.addView(emptyCard, matchWrap());
        }
        addSpace(column, 8);
        column.addView(label("The Telegram bot processes one media job at a time.", 12, MUTED, false), matchWrap());
        return scroll;
    }

    private View makeJobCard(DownloadRecord record) {
        MaterialCardView outer = card();
        LinearLayout content = paddedColumn(14);
        outer.addView(content);
        LinearLayout heading = newRow();
        TextView tile = label(record.isCompleted() ? "✓" : "▶", 18, record.isCompleted() ? INK : LIME, true);
        tile.setGravity(Gravity.CENTER);
        tile.setBackground(rounded(record.isCompleted() ? LIME : SURFACE_2, 16));
        heading.addView(tile, new LinearLayout.LayoutParams(dp(48), dp(48)));
        addSpaceHorizontal(heading, 12);
        LinearLayout titleBlock = newColumn();
        titleBlock.addView(label(record.title, 16, TEXT, true), matchWrap());
        addSpace(titleBlock, 3);
        titleBlock.addView(label(record.choiceLabel, 13, MUTED, false), matchWrap());
        heading.addView(titleBlock, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        content.addView(heading, matchWrap());
        addSpace(content, 12);
        LinearLayout statusRow = newRow();
        statusRow.addView(label(friendlyStatus(record), 13, record.isCompleted() ? LIME : MUTED, false),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        statusRow.addView(label(record.isCompleted() ? "100%" : record.progress + "%", 12, MUTED, false), wrap());
        content.addView(statusRow, matchWrap());
        addSpace(content, 6);
        ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgress(record.isCompleted() ? 100 : record.progress);
        progress.setProgressTintList(ColorStateList.valueOf(LIME));
        progress.setProgressBackgroundTintList(ColorStateList.valueOf(OUTLINE));
        content.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(6)));
        if (!TextUtils.isEmpty(record.statusText)) {
            addSpace(content, 7);
            content.addView(label(record.statusText, 12, MUTED, false), matchWrap());
        }
        if (record.isCompleted()) {
            addSpace(content, 11);
            TextView delivery = label("Sent to Telegram · open @" + botUsername, 13, LIME, true);
            delivery.setOnClickListener(v -> openTelegram());
            content.addView(delivery, matchWrap());
        }
        return outer;
    }

    private View makeSettingsPage() {
        ScrollView scroll = newScrollPage();
        LinearLayout column = newColumn();
        scroll.addView(column);
        column.addView(label("Settings", 29, TEXT, true), matchWrap());
        addSpace(column, 22);
        column.addView(sectionHeading("DOWNLOADS"), matchWrap());
        addSpace(column, 9);

        MaterialCardView downloadCard = card();
        LinearLayout downloadSettings = paddedColumn(4);
        downloadCard.addView(downloadSettings);
        String quality = preferences.getString(QUALITY_KEY, "720p");
        View qualityButton = settingRow("▣", "Default quality", quality);
        qualityButton.setOnClickListener(v -> cycleQuality());
        downloadSettings.addView(qualityButton, matchWrap());
        addDivider(downloadSettings);
        View deliveryButton = settingRow("▱", "Delivery", "Telegram");
        deliveryButton.setOnClickListener(v -> new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Telegram delivery")
                .setMessage("The K2App server sends the finished media directly to your paired Telegram chat. K2 Lite tracks the job; it does not keep a second copy of the media on this phone.")
                .setPositiveButton("Got it", null).show());
        downloadSettings.addView(deliveryButton, matchWrap());
        addDivider(downloadSettings);
        LinearLayout wifiRow = newRow();
        TextView wifiIcon = label("◉", 21, MUTED, true);
        wifiRow.addView(wifiIcon, new LinearLayout.LayoutParams(dp(40), ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout wifiLabels = newColumn();
        wifiLabels.addView(label("Wi-Fi only", 15, TEXT, true), matchWrap());
        wifiLabels.addView(label("Use mobile data only when switched off", 12, MUTED, false), matchWrap());
        wifiRow.addView(wifiLabels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        SwitchMaterial wifiSwitch = new SwitchMaterial(this);
        wifiSwitch.setButtonTintList(ColorStateList.valueOf(LIME));
        wifiSwitch.setChecked(preferences.getBoolean(WIFI_ONLY_KEY, true));
        wifiSwitch.setOnCheckedChangeListener((button, checked) -> preferences.edit().putBoolean(WIFI_ONLY_KEY, checked).apply());
        wifiRow.addView(wifiSwitch, wrap());
        wifiRow.setPadding(dp(10), dp(14), dp(10), dp(14));
        downloadSettings.addView(wifiRow, matchWrap());
        column.addView(downloadCard, matchWrap());

        addSpace(column, 22);
        column.addView(sectionHeading("TELEGRAM PAIRING"), matchWrap());
        addSpace(column, 9);
        MaterialCardView pairingCard = card();
        LinearLayout pairing = paddedColumn(16);
        pairingCard.addView(pairing);
        String storedToken = tokenStore.read();
        TextView connection = label(storedToken == null ? "Not connected" : "●  Connected to @" + botUsername,
                16, storedToken == null ? MUTED : LIME, true);
        pairing.addView(connection, matchWrap());
        addSpace(pairing, 6);
        pairing.addView(label("Send /pair to @" + botUsername + " in Telegram. Enter the one-use code here within 5 minutes.",
                13, MUTED, false), matchWrap());
        addSpace(pairing, 12);
        TextInputLayout codeLayout = new TextInputLayout(this);
        codeLayout.setHint("One-time pairing code");
        codeLayout.setBoxBackgroundMode(TextInputLayout.BOX_BACKGROUND_OUTLINE);
        codeLayout.setBoxStrokeColor(OUTLINE);
        codeLayout.setHintTextColor(ColorStateList.valueOf(MUTED));
        codeLayout.setBoxCornerRadii(dp(18), dp(18), dp(18), dp(18));
        pairingInput = new TextInputEditText(codeLayout.getContext());
        pairingInput.setSingleLine(true);
        pairingInput.setTextColor(TEXT);
        pairingInput.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        pairingInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        codeLayout.addView(pairingInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        pairing.addView(codeLayout, matchWrap());
        addSpace(pairing, 10);
        MaterialButton pairButton = primaryButton(storedToken == null ? "Connect Telegram" : "Pair another device");
        pairButton.setOnClickListener(v -> pairDevice());
        pairing.addView(pairButton, matchWrap());
        if (!TextUtils.isEmpty(pairingMessage)) {
            addSpace(pairing, 8);
            pairing.addView(label(pairingMessage, 13, ERROR, false), matchWrap());
        }
        if (storedToken != null) {
            addSpace(pairing, 6);
            TextView disconnect = label("Disconnect this device", 13, MUTED, false);
            disconnect.setPadding(0, dp(8), 0, dp(4));
            disconnect.setOnClickListener(v -> confirmDisconnect());
            pairing.addView(disconnect, matchWrap());
        }
        column.addView(pairingCard, matchWrap());

        addSpace(column, 22);
        column.addView(sectionHeading("APP"), matchWrap());
        addSpace(column, 9);
        MaterialCardView appCard = card();
        LinearLayout appSettings = paddedColumn(4);
        appCard.addView(appSettings);
        View theme = settingRow("◐", "Theme", "Dark");
        theme.setOnClickListener(v -> new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Theme").setMessage("K2 Lite uses the approved dark charcoal and lime-green theme.")
                .setPositiveButton("OK", null).show());
        appSettings.addView(theme, matchWrap());
        addDivider(appSettings);
        View storage = settingRow("▤", "Local history", jobs.size() + " jobs");
        storage.setOnClickListener(v -> { section = Section.DOWNLOADS; completedTab = true; render(); });
        appSettings.addView(storage, matchWrap());
        addDivider(appSettings);
        View about = settingRow("ⓘ", "About K2App Lite", "v" + BuildConfig.VERSION_NAME);
        about.setOnClickListener(v -> new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("K2App Lite")
                .setMessage("A lightweight Material 3 client for the K2App Telegram media service. Pair with the bot to analyze public links, select an available format and follow delivery status.")
                .setPositiveButton("Close", null).show());
        appSettings.addView(about, matchWrap());
        column.addView(appCard, matchWrap());
        addSpace(column, 22);
        TextView footer = label("Lightweight by design", 13, MUTED, false);
        footer.setGravity(Gravity.CENTER);
        column.addView(footer, matchWrap());
        addSpace(column, 14);
        return scroll;
    }

    private View settingRow(String glyph, String title, String value) {
        LinearLayout row = newRow();
        row.setPadding(dp(10), dp(12), dp(8), dp(12));
        row.setBackground(rounded(SURFACE, 14));
        row.setMinimumHeight(dp(56));
        TextView icon = label(glyph, 20, MUTED, true);
        icon.setGravity(Gravity.CENTER);
        row.addView(icon, new LinearLayout.LayoutParams(dp(38), ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout text = newColumn();
        text.addView(label(title, 15, TEXT, true), matchWrap());
        row.addView(text, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView valueText = label(value, 13, MUTED, false);
        valueText.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        row.addView(valueText, wrap());
        TextView arrow = label("›", 24, MUTED, false);
        arrow.setGravity(Gravity.CENTER);
        row.addView(arrow, new LinearLayout.LayoutParams(dp(24), ViewGroup.LayoutParams.WRAP_CONTENT));
        return row;
    }

    private View sectionHeading(String title) {
        TextView view = label(title, 13, MUTED, true);
        view.setLetterSpacing(0.12f);
        view.setPadding(dp(4), dp(2), dp(4), dp(2));
        return view;
    }

    private void analyzeLink(String rawUrl) {
        String value = rawUrl == null ? "" : rawUrl.trim();
        if (value.isEmpty()) {
            homeMessage = "Paste a public video or audio link first.";
            render();
            return;
        }
        String token = tokenStore.read();
        if (token == null) {
            pairingMessage = "Pair with the Telegram bot before analyzing a link.";
            section = Section.SETTINGS;
            showingOptions = false;
            render();
            return;
        }
        if (preferences.getBoolean(WIFI_ONLY_KEY, true) && !isOnWifi()) {
            homeMessage = "Wi-Fi only is on. Connect to Wi-Fi or switch it off in Settings.";
            render();
            return;
        }
        pendingUrl = value;
        homeMessage = "Checking available formats…";
        render();
        io.execute(() -> {
            try {
                JSONObject result = api.analyze(value, token);
                runOnUiThread(() -> {
                    homeMessage = "";
                    pendingJob = result;
                    pendingChoices = result.optJSONArray("choices");
                    selectedKind = firstAvailableKind(pendingChoices);
                    selectedChoice = preferredChoice(pendingChoices, preferences.getString(QUALITY_KEY, "720p"));
                    showingOptions = true;
                    render();
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    homeMessage = safeMessage(failure);
                    if (failure instanceof LiteApi.ApiException
                            && ((LiteApi.ApiException) failure).statusCode == 401) {
                        tokenStore.clear();
                        homeMessage = "Pairing expired. Reconnect in Settings.";
                    }
                    render();
                });
            }
        });
    }

    private void startSelectedDownload() {
        if (pendingJob == null || pendingChoices == null || selectedChoice < 0
                || selectedChoice >= pendingChoices.length()) {
            showToast("Choose an available format first.");
            return;
        }
        String token = tokenStore.read();
        if (token == null) {
            showingOptions = false;
            section = Section.SETTINGS;
            render();
            return;
        }
        JSONObject choice = pendingChoices.optJSONObject(selectedChoice);
        String choiceLabel = choice == null ? "Media" : choice.optString("label", "Media");
        String jobId = pendingJob.optString("job_id", "");
        if (jobId.isEmpty()) {
            showToast("The service did not return a job ID. Please try again.");
            return;
        }
        MaterialButton sourceButton = null;
        hideKeyboard();
        io.execute(() -> {
            try {
                api.choose(jobId, selectedChoice, token);
                runOnUiThread(() -> {
                    JSONObject media = pendingJob == null ? null : pendingJob.optJSONObject("media");
                    String title = media == null ? "Media" : media.optString("title", "Media");
                    DownloadRecord record = new DownloadRecord(jobId, title, pendingUrl, choiceLabel);
                    jobs.removeIf(existing -> existing.jobId.equals(jobId));
                    jobs.add(0, record);
                    saveJobs();
                    showingOptions = false;
                    section = Section.DOWNLOADS;
                    completedTab = false;
                    render();
                    showToast("Added to the Telegram delivery queue.");
                    schedulePoll(1_000);
                });
            } catch (Exception failure) {
                runOnUiThread(() -> showToast(safeMessage(failure)));
            }
        });
    }

    private void pairDevice() {
        if (pairingInput == null) return;
        String code = String.valueOf(pairingInput.getText()).trim();
        if (code.isEmpty()) {
            pairingMessage = "Enter the one-time code from Telegram.";
            render();
            return;
        }
        if (preferences.getBoolean(WIFI_ONLY_KEY, true) && !isOnWifi()) {
            pairingMessage = "Wi-Fi only is on. Connect to Wi-Fi or switch it off above.";
            render();
            return;
        }
        pairingMessage = "Connecting securely…";
        render();
        io.execute(() -> {
            try {
                JSONObject response = api.pair(code);
                String accessToken = response.optString("access_token", "");
                if (accessToken.isEmpty()) throw new IOException("The service did not return an access token.");
                tokenStore.save(accessToken);
                runOnUiThread(() -> {
                    pairingMessage = "Device paired successfully.";
                    render();
                    showToast("K2 Lite is connected.");
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    pairingMessage = safeMessage(failure);
                    render();
                });
            }
        });
    }

    private void fetchServiceIdentity() {
        io.execute(() -> {
            try {
                JSONObject status = api.serviceStatus();
                String receivedUrl = status.optString("bot_url", "");
                String receivedName = status.optString("bot_username", "");
                if (!receivedUrl.isEmpty() && receivedUrl.startsWith("https://t.me/")) botUrl = receivedUrl;
                if (!receivedName.isEmpty()) botUsername = receivedName;
                runOnUiThread(() -> {
                    if (section == Section.SETTINGS && !showingOptions) render();
                });
            } catch (Exception ignored) {
                // Keep the known public bot link as a graceful offline fallback.
            }
        });
    }

    private void schedulePoll(long delayMs) {
        if (!activityResumed || pollInFlight) return;
        handler.removeCallbacks(pollRunnable);
        handler.postDelayed(pollRunnable, delayMs);
    }

    private void pollActiveJobs() {
        if (!activityResumed || pollInFlight) return;
        String token = tokenStore.read();
        if (token == null) return;
        List<DownloadRecord> active = new ArrayList<>();
        for (DownloadRecord job : jobs) if (!job.isCompleted()) active.add(job);
        if (active.isEmpty()) return;
        pollInFlight = true;
        io.execute(() -> {
            boolean tokenExpired = false;
            for (DownloadRecord record : active) {
                try {
                    JSONObject response = api.job(record.jobId, token);
                    record.status = response.optString("status", record.status);
                    record.progress = Math.max(0, Math.min(100, response.optInt("progress", record.progress)));
                    record.statusText = response.optString("status_text", record.statusText);
                    if ("done".equalsIgnoreCase(record.status)) {
                        record.progress = 100;
                        if (TextUtils.isEmpty(record.statusText)) record.statusText = "Ready in your Telegram chat.";
                    }
                } catch (LiteApi.ApiException failure) {
                    if (failure.statusCode == 401) {
                        tokenExpired = true;
                        break;
                    }
                    if (failure.statusCode == 404) record.statusText = "Job expired on the service. You can remove it from history.";
                } catch (Exception ignored) {
                    // Keep the latest known progress; the next foreground poll will retry.
                }
            }
            final boolean expired = tokenExpired;
            if (expired) tokenStore.clear();
            saveJobs();
            runOnUiThread(() -> {
                pollInFlight = false;
                if (expired && section == Section.SETTINGS) {
                    pairingMessage = "Pairing expired. Send /pair to the bot and connect again.";
                }
                if (section == Section.DOWNLOADS && !showingOptions) render();
                schedulePoll(15_000);
            });
        });
    }

    private void clearFinished() {
        int before = jobs.size();
        jobs.removeIf(DownloadRecord::isCompleted);
        saveJobs();
        render();
        showToast(before == jobs.size() ? "No finished jobs to clear." : "Finished jobs removed from this device.");
    }

    private void confirmDisconnect() {
        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Disconnect this device?")
                .setMessage("This removes the saved pairing token from this phone. It does not delete Telegram files or server history.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Disconnect", (dialog, which) -> {
                    tokenStore.clear();
                    pairingMessage = "Device disconnected.";
                    render();
                }).show();
    }

    private void cycleQuality() {
        String current = preferences.getString(QUALITY_KEY, "720p");
        String next = "720p".equals(current) ? "1080p" : "1080p".equals(current) ? "480p" : "720p";
        preferences.edit().putString(QUALITY_KEY, next).apply();
        render();
    }

    private void pasteFromClipboard() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        if (clipboard == null || !clipboard.hasPrimaryClip()) {
            showToast("Nothing to paste yet.");
            return;
        }
        ClipData clip = clipboard.getPrimaryClip();
        if (clip == null || clip.getItemCount() == 0) return;
        CharSequence value = clip.getItemAt(0).coerceToText(this);
        if (urlInput != null && value != null) {
            urlInput.setText(value.toString().trim());
            urlInput.setSelection(urlInput.length());
        }
    }

    private void openTelegram() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(botUrl)));
        } catch (Exception failure) {
            showToast("Could not open Telegram.");
        }
    }

    private void loadThumbnail(String value, ImageView target) {
        if (TextUtils.isEmpty(value) || !value.startsWith("https://")) return;
        io.execute(() -> {
            HttpURLConnection connection = null;
            try {
                URL url = new URL(value);
                if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getUserInfo() != null) return;
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(5_000);
                connection.setReadTimeout(8_000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("User-Agent", "K2App-Lite/1.0");
                if (connection.getResponseCode() != 200) return;
                Bitmap bitmap = BitmapFactory.decodeStream(connection.getInputStream());
                if (bitmap != null) runOnUiThread(() -> target.setImageBitmap(bitmap));
            } catch (Exception ignored) {
                // Thumbnails are optional; the screen remains usable if one cannot load.
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void loadJobs() {
        jobs.clear();
        jobs.addAll(DownloadRecord.parseList(preferences.getString(JOBS_KEY, "")));
    }

    private void saveJobs() {
        JSONArray array = new JSONArray();
        try {
            for (DownloadRecord job : jobs) array.put(job.toJson());
            preferences.edit().putString(JOBS_KEY, array.toString()).apply();
        } catch (JSONException ignored) {
            // Keep the last saved job list if a local serialization error occurs.
        }
    }

    private List<DownloadRecord> sortedJobs() {
        List<DownloadRecord> result = new ArrayList<>(jobs);
        Collections.sort(result, Comparator.comparingLong((DownloadRecord job) -> job.createdAt).reversed());
        return result;
    }

    private String firstAvailableKind(JSONArray choices) {
        if (choices == null) return "video";
        for (int i = 0; i < choices.length(); i++) {
            JSONObject choice = choices.optJSONObject(i);
            if (choice != null && "video".equals(choice.optString("kind"))) return "video";
        }
        for (int i = 0; i < choices.length(); i++) {
            JSONObject choice = choices.optJSONObject(i);
            if (choice != null) return choice.optString("kind", "video");
        }
        return "video";
    }

    private int firstChoiceOfKind(String kind) {
        if (pendingChoices == null) return -1;
        for (int i = 0; i < pendingChoices.length(); i++) {
            JSONObject choice = pendingChoices.optJSONObject(i);
            if (choice != null && kind.equals(choice.optString("kind", "video"))) return i;
        }
        return -1;
    }

    private int preferredChoice(JSONArray choices, String quality) {
        if (choices == null || choices.length() == 0) return -1;
        int fallback = -1;
        int bestHeight = -1;
        int requested = parseQuality(quality);
        for (int i = 0; i < choices.length(); i++) {
            JSONObject choice = choices.optJSONObject(i);
            if (choice == null || !"video".equals(choice.optString("kind"))) continue;
            if (fallback < 0) fallback = i;
            int height = choice.optInt("height", 0);
            if (height == requested) return i;
            if (height <= requested && height > bestHeight) {
                bestHeight = height;
                fallback = i;
            }
        }
        if (fallback >= 0) return fallback;
        return 0;
    }

    private int parseQuality(String quality) {
        try { return Integer.parseInt(quality.replace("p", "")); }
        catch (Exception ignored) { return 720; }
    }

    private boolean hasChoiceKind(String kind) {
        if (pendingChoices == null) return false;
        for (int i = 0; i < pendingChoices.length(); i++) {
            JSONObject choice = pendingChoices.optJSONObject(i);
            if (choice != null && kind.equals(choice.optString("kind"))) return true;
        }
        return false;
    }

    private boolean isRecommended(JSONObject choice) {
        if (choice == null) return false;
        if ("audio".equals(choice.optString("kind"))) return choice.optInt("audio_quality", 0) == 192;
        int height = choice.optInt("height", 0);
        return height == 720 || (height > 0 && height <= 720 && !hasHeightAbove(height));
    }

    private boolean hasHeightAbove(int height) {
        if (pendingChoices == null) return false;
        for (int i = 0; i < pendingChoices.length(); i++) {
            JSONObject choice = pendingChoices.optJSONObject(i);
            if (choice != null && "video".equals(choice.optString("kind")) && choice.optInt("height", 0) > height) return true;
        }
        return false;
    }

    private String videoDetail(JSONObject choice) {
        int height = choice.optInt("height", 0);
        return height > 0 ? height + "p video" : "Best available video";
    }

    private String friendlyStatus(DownloadRecord record) {
        if (record.isCompleted()) return "Ready in Telegram";
        String status = record.status == null ? "" : record.status.toLowerCase(Locale.ROOT);
        if ("queued".equals(status)) return "Waiting in queue";
        if ("downloading".equals(status)) return "Downloading · " + record.progress + "%";
        if ("preparing".equals(status)) return "Preparing media";
        if ("uploading".equals(status)) return "Sending to Telegram";
        if ("failed".equals(status)) return "Transfer failed";
        return "Processing";
    }

    private String safeMessage(Exception failure) {
        String message = failure.getMessage();
        if (TextUtils.isEmpty(message)) return "The request failed. Check your connection and try again.";
        if (message.length() > 180) message = message.substring(0, 177) + "…";
        return message;
    }

    private String shortUrl(String value) {
        if (TextUtils.isEmpty(value)) return "";
        return value.length() > 42 ? value.substring(0, 39) + "…" : value;
    }

    private String getSharedMediaText(Intent intent) {
        if (intent == null) return null;
        if (Intent.ACTION_SEND.equals(intent.getAction())) return intent.getStringExtra(Intent.EXTRA_TEXT);
        if (Intent.ACTION_VIEW.equals(intent.getAction()) && intent.getData() != null) return intent.getData().toString();
        return null;
    }

    private boolean isOnWifi() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (manager == null) return false;
        NetworkCapabilities capabilities = manager.getNetworkCapabilities(manager.getActiveNetwork());
        return capabilities != null && capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
    }

    private void hideKeyboard() {
        View current = getCurrentFocus();
        if (current != null) {
            InputMethodManager manager = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            if (manager != null) manager.hideSoftInputFromWindow(current.getWindowToken(), 0);
        }
    }

    private void showToast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_LONG).show();
    }

    private MaterialCardView card() {
        MaterialCardView view = new MaterialCardView(this);
        view.setCardBackgroundColor(SURFACE);
        view.setStrokeColor(OUTLINE);
        view.setStrokeWidth(dp(1));
        view.setRadius(dp(22));
        view.setCardElevation(0f);
        return view;
    }

    private LinearLayout paddedColumn(int padding) {
        LinearLayout column = newColumn();
        column.setPadding(dp(padding), dp(padding), dp(padding), dp(padding));
        return column;
    }

    private TextView label(String value, int sizeSp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER_VERTICAL);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setIncludeFontPadding(false);
        return view;
    }

    private MaterialButton primaryButton(String caption) {
        MaterialButton button = new MaterialButton(this);
        button.setText(caption);
        button.setAllCaps(false);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        button.setTextColor(INK);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setCornerRadius(dp(17));
        button.setInsetTop(0);
        button.setInsetBottom(0);
        button.setMinHeight(dp(54));
        button.setBackgroundTintList(ColorStateList.valueOf(LIME));
        return button;
    }

    private MaterialButton smallTextButton(String caption, boolean selected) {
        MaterialButton button = new MaterialButton(this);
        button.setText(caption);
        button.setAllCaps(false);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setTextColor(selected ? INK : MUTED);
        button.setCornerRadius(dp(18));
        button.setInsetTop(0);
        button.setInsetBottom(0);
        button.setBackgroundTintList(ColorStateList.valueOf(selected ? LIME : SURFACE_2));
        button.setStrokeColor(ColorStateList.valueOf(selected ? LIME : OUTLINE));
        button.setStrokeWidth(dp(1));
        return button;
    }

    private MaterialButton smallTextButton(String caption, boolean selected, int minHeight) {
        MaterialButton button = smallTextButton(caption, selected);
        button.setMinHeight(dp(minHeight));
        return button;
    }

    private void addDivider(LinearLayout parent) {
        View line = new View(this);
        line.setBackgroundColor(OUTLINE);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(1));
        params.leftMargin = dp(8);
        params.rightMargin = dp(8);
        parent.addView(line, params);
    }

    private GradientDrawable rounded(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        return drawable;
    }

    private void addSpace(LinearLayout parent, int heightDp) {
        View space = new View(this);
        parent.addView(space, new LinearLayout.LayoutParams(1, dp(heightDp)));
    }

    private void addSpaceHorizontal(LinearLayout parent, int widthDp) {
        View space = new View(this);
        parent.addView(space, new LinearLayout.LayoutParams(dp(widthDp), 1));
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
