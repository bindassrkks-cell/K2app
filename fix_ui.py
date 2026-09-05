import os

# 1. Create drawables folder if missing
drawable_dir = 'app/src/main/res/drawable'
os.makedirs(drawable_dir, exist_ok=True)

# 2. Vector Icons Definitions
icons = {
    'ic_play.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M8,5v14l11,-7z"/>
</vector>''',

    'ic_search.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M15.5,14h-0.79l-0.28,-0.27C15.41,12.59 16,11.11 16,9.5 16,5.91 13.09,3 9.5,3S3,5.91 3,9.5 5.91,16 9.5,16c1.61,0 3.09,-0.59 4.23,-1.57l0.27,0.28v0.79l5,4.99L20.49,19l-4.99,-5zm-6,0C7.01,14 5,11.99 5,9.5S7.01,5 9.5,5 14,7.01 14,9.5 11.99,14 9.5,14z"/>
</vector>''',

    'ic_settings.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M19.14,12.94c0.04,-0.3 0.06,-0.61 0.06,-0.94 0,-0.32 -0.02,-0.64 -0.07,-0.94l2.03,-1.58c0.18,-0.14 0.23,-0.41 0.12,-0.61l-1.92,-3.32c-0.12,-0.22 -0.37,-0.29 -0.59,-0.22l-2.39,0.96c-0.5,-0.38 -1.03,-0.7 -1.62,-0.94L14.4,2.81c-0.04,-0.24 -0.24,-0.41 -0.48,-0.41h-3.84c-0.24,0 -0.43,0.17 -0.47,0.41L9.25,5.35C8.66,5.59 8.12,5.92 7.63,6.29L5.24,5.33c-0.22,-0.08 -0.47,0 -0.59,0.22L2.74,8.87c-0.12,0.21 -0.08,0.47 0.12,0.61l2.03,1.58c-0.05,0.3 -0.09,0.63 -0.09,0.94s0.02,0.64 0.07,0.94l-2.03,1.58c-0.18,0.14 -0.23,0.41 -0.12,0.61l1.92,3.32c0.12,0.22 0.37,0.29 0.59,0.22l2.39,-0.96c0.5,0.38 1.03,0.7 1.62,0.94l0.36,2.54c0.05,0.24 0.24,0.41 0.48,0.41h3.84c0.24,0 0.44,-0.17 0.47,-0.41l0.36,-2.54c0.59,-0.24 1.13,-0.56 1.62,-0.94l2.39,0.96c0.22,0.08 0.47,0 0.59,-0.22l1.92,-3.32c0.12,-0.22 0.07,-0.47 -0.12,-0.61l-2.01,-1.58zM12,15.6c-1.98,0 -3.6,-1.62 -3.6,-3.6s1.62,-3.6 3.6,-3.6 3.6,1.62 3.6,3.6 -1.62,3.6 -3.6,3.6z"/>
</vector>''',

    'ic_history.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M13,3c-4.97,0 -9,4.03 -9,9H1l3.89,3.89 0.07,0.14L9,12H6c0,-3.87 3.13,-7 7,-7s7,3.13 7,7 -3.13,7 -7,7c-1.93,0 -3.68,-0.79 -4.94,-2.06l-1.42,1.42C8.27,19.99 10.51,21 13,21c4.97,0 9,-4.03 9,-9s-4.03,-9 -9,-9zm-1,5v5l4.28,2.54 0.72,-1.21 -3.5,-2.08V8H12z"/>
</vector>''',

    'ic_download.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M19,9h-4V3H9v6H5l7,7 7,-7zM5,18v2h14v-2H5z"/>
</vector>''',

    'ic_link.xml': '''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M3.9,12c0,-1.71 1.39,-3.1 3.1,-3.1h4V7H7c-2.76,0 -5,2.24 -5,5s2.24,5 5,5h4v-1.9H7c-1.71,0 -3.1,-1.39 -3.1,-3.1zM8,13h8v-2H8v2zm9,-6h-4v1.9h4c1.71,0 3.1,1.39 3.1,3.1s-1.39,3.1 -3.1,3.1h-4V17h4c2.76,0 5,-2.24 5,-5s-2.24,-5 -5,-5z"/>
</vector>'''
}

for name, content in icons.items():
    with open(os.path.join(drawable_dir, name), 'w') as f:
        f.write(content)

# 3. Write 100% Self-Contained fragment_home.xml
home_xml = '''<?xml version="1.0" encoding="utf-8"?>
<androidx.coordinatorlayout.widget.CoordinatorLayout 
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#4FC3F7">

    <com.google.android.material.appbar.AppBarLayout
        android:id="@+id/home_appbarlayout"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:background="#4FC3F7"
        app:elevation="0dp">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="60dp"
            android:orientation="horizontal"
            android:gravity="center_vertical"
            android:paddingHorizontal="16dp">

            <LinearLayout
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                android:layout_weight="1"
                android:gravity="center_vertical"
                android:orientation="horizontal">

                <com.google.android.material.card.MaterialCardView
                    android:layout_width="38dp"
                    android:layout_height="38dp"
                    app:cardCornerRadius="19dp"
                    app:cardBackgroundColor="#FFFFFF"
                    app:cardElevation="0dp"
                    app:strokeWidth="0dp">
                    <ImageView
                        android:id="@+id/header_app_logo"
                        android:layout_width="match_parent"
                        android:layout_height="match_parent"
                        android:padding="8dp"
                        android:src="@drawable/ic_play"
                        app:tint="#FF0000" />
                </com.google.android.material.card.MaterialCardView>

                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:layout_marginStart="10dp"
                    android:text="Kupido Player"
                    android:textColor="#FFFFFF"
                    android:textSize="21sp"
                    android:textStyle="bold" />
            </LinearLayout>

            <ImageView
                android:id="@+id/btn_quick_search"
                android:layout_width="42dp"
                android:layout_height="42dp"
                android:clickable="true"
                android:focusable="true"
                android:padding="9dp"
                android:src="@drawable/ic_search"
                app:tint="#FFFFFF" />

            <ImageView
                android:id="@+id/btn_settings"
                android:layout_width="42dp"
                android:layout_height="42dp"
                android:layout_marginStart="4dp"
                android:clickable="true"
                android:focusable="true"
                android:padding="8dp"
                android:src="@drawable/ic_settings"
                app:tint="#FFFFFF" />
        </LinearLayout>

        <HorizontalScrollView
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:scrollbars="none"
            android:paddingStart="14dp"
            android:paddingEnd="14dp"
            android:paddingBottom="8dp"
            android:clipToPadding="false">

            <LinearLayout
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:orientation="horizontal"
                android:gravity="center_vertical">

                <com.google.android.material.card.MaterialCardView
                    android:id="@+id/pill_history"
                    android:layout_width="wrap_content"
                    android:layout_height="38dp"
                    android:layout_marginEnd="8dp"
                    app:cardCornerRadius="19dp"
                    app:cardBackgroundColor="#1A1C1E"
                    app:cardElevation="0dp"
                    app:strokeWidth="0dp"
                    android:clickable="true"
                    android:focusable="true">
                    <LinearLayout
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:gravity="center"
                        android:paddingHorizontal="14dp">
                        <ImageView
                            android:layout_width="18dp"
                            android:layout_height="18dp"
                            android:src="@drawable/ic_history"
                            app:tint="#FFFFFF" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginStart="6dp"
                            android:text="Watch again"
                            android:textColor="#FFFFFF"
                            android:textStyle="bold"
                            android:textSize="13sp" />
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>

                <com.google.android.material.card.MaterialCardView
                    android:id="@+id/pill_downloads"
                    android:layout_width="wrap_content"
                    android:layout_height="38dp"
                    android:layout_marginEnd="8dp"
                    app:cardCornerRadius="19dp"
                    app:cardBackgroundColor="#FFFFFF"
                    app:cardElevation="0dp"
                    app:strokeWidth="1dp"
                    app:strokeColor="#E0E0E0"
                    android:clickable="true"
                    android:focusable="true">
                    <LinearLayout
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:gravity="center"
                        android:paddingHorizontal="14dp">
                        <ImageView
                            android:layout_width="18dp"
                            android:layout_height="18dp"
                            android:src="@drawable/ic_download"
                            app:tint="#212121" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginStart="6dp"
                            android:text="Downloads"
                            android:textColor="#212121"
                            android:textStyle="bold"
                            android:textSize="13sp" />
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>

                <com.google.android.material.card.MaterialCardView
                    android:id="@+id/pill_input_url"
                    android:layout_width="wrap_content"
                    android:layout_height="38dp"
                    android:layout_marginEnd="8dp"
                    app:cardCornerRadius="19dp"
                    app:cardBackgroundColor="#FFFFFF"
                    app:cardElevation="0dp"
                    app:strokeWidth="1dp"
                    app:strokeColor="#E0E0E0"
                    android:clickable="true"
                    android:focusable="true">
                    <LinearLayout
                        android:layout_width="wrap_content"
                        android:layout_height="match_parent"
                        android:gravity="center"
                        android:paddingHorizontal="14dp">
                        <ImageView
                            android:layout_width="18dp"
                            android:layout_height="18dp"
                            android:src="@drawable/ic_link"
                            app:tint="#212121" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginStart="6dp"
                            android:text="Paste URL"
                            android:textColor="#212121"
                            android:textStyle="bold"
                            android:textSize="13sp" />
                    </LinearLayout>
                </com.google.android.material.card.MaterialCardView>

                <HorizontalScrollView
                    android:id="@+id/playlist_selection_chips_scrollview"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:visibility="gone">
                    <com.google.android.material.chip.ChipGroup
                        android:id="@+id/playlist_selection_chips"
                        android:layout_width="wrap_content"
                        android:layout_height="wrap_content"
                        app:singleSelection="true" />
                </HorizontalScrollView>
            </LinearLayout>
        </HorizontalScrollView>

        <com.google.android.material.appbar.MaterialToolbar
            android:id="@+id/home_toolbar"
            android:layout_width="match_parent"
            android:layout_height="0dp"
            android:visibility="gone" />

        <com.google.android.material.search.SearchBar
            android:id="@+id/search_bar"
            android:layout_width="match_parent"
            android:layout_height="48dp"
            android:layout_marginHorizontal="14dp"
            android:layout_marginBottom="8dp"
            android:hint="Search or paste link..."
            app:backgroundTint="#FFFFFF"
            android:elevation="2dp" />

    </com.google.android.material.appbar.AppBarLayout>

    <androidx.constraintlayout.widget.ConstraintLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        app:layout_behavior="@string/appbar_scrolling_view_behavior">

        <com.facebook.shimmer.ShimmerFrameLayout
            android:id="@+id/shimmer_results_framelayout"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:visibility="gone">
            <LinearLayout
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:orientation="vertical"
                android:padding="12dp">
                <View
                    android:layout_width="match_parent"
                    android:layout_height="220dp"
                    android:background="#B3E5FC"
                    android:layout_marginBottom="14dp" />
            </LinearLayout>
        </com.facebook.shimmer.ShimmerFrameLayout>

        <androidx.recyclerview.widget.RecyclerView
            android:id="@+id/recyclerViewHome"
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:paddingHorizontal="12dp"
            android:paddingTop="6dp"
            android:paddingBottom="90dp"
            android:clipToPadding="false" />

        <androidx.constraintlayout.widget.ConstraintLayout
            android:id="@+id/queries_constraint"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:visibility="gone"
            android:background="#E1F5FE"
            android:padding="8dp"
            app:layout_constraintTop_toTopOf="parent">

            <com.google.android.material.chip.ChipGroup
                android:id="@+id/queries"
                android:layout_width="0dp"
                android:layout_height="wrap_content"
                app:layout_constraintStart_toStartOf="parent"
                app:layout_constraintEnd_toStartOf="@+id/init_search_query"
                app:layout_constraintTop_toTopOf="parent" />

            <com.google.android.material.button.MaterialButton
                android:id="@+id/init_search_query"
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:text="Start"
                app:layout_constraintEnd_toEndOf="parent"
                app:layout_constraintTop_toTopOf="parent" />
        </androidx.constraintlayout.widget.ConstraintLayout>

        <ProgressBar
            android:id="@+id/progress"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:visibility="gone"
            app:layout_constraintBottom_toBottomOf="parent"
            app:layout_constraintEnd_toEndOf="parent"
            app:layout_constraintStart_toStartOf="parent"
            app:layout_constraintTop_toTopOf="parent" />

    </androidx.constraintlayout.widget.ConstraintLayout>

    <LinearLayout
        android:id="@+id/home_fabs"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:orientation="vertical"
        android:layout_gravity="bottom|end"
        android:layout_margin="16dp">

        <com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
            android:id="@+id/copied_url_fab"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Paste &amp; Download"
            android:visibility="gone"
            android:layout_marginBottom="8dp"
            app:icon="@drawable/ic_link"
            android:backgroundTint="#FFFFFF"
            android:textColor="#000000"
            app:iconTint="#000000" />

        <com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
            android:id="@+id/download_selected_fab"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Download Selected"
            android:visibility="gone"
            android:layout_marginBottom="8dp"
            app:icon="@drawable/ic_download"
            android:backgroundTint="#212121"
            android:textColor="#FFFFFF" />

        <com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
            android:id="@+id/download_all_fab"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:text="Download Playlist"
            android:visibility="gone"
            app:icon="@drawable/ic_download"
            android:backgroundTint="#D32F2F"
            android:textColor="#FFFFFF"
            app:iconTint="#FFFFFF" />
    </LinearLayout>

    <com.google.android.material.search.SearchView
        android:id="@+id/search_view"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:hint="Search music, videos, channels..."
        app:layout_anchor="@id/search_bar">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="match_parent"
            android:orientation="vertical">

            <HorizontalScrollView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:padding="8dp">
                <com.google.android.material.chip.ChipGroup
                    android:id="@+id/providers"
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    app:singleSelection="true" />
            </HorizontalScrollView>

            <View
                android:id="@+id/chipGroupDivider"
                android:layout_width="match_parent"
                android:layout_height="1dp"
                android:background="#E0E0E0" />

            <androidx.recyclerview.widget.RecyclerView
                android:id="@+id/search_suggestions_recycler"
                android:layout_width="match_parent"
                android:layout_height="match_parent" />
        </LinearLayout>
    </com.google.android.material.search.SearchView>

</androidx.coordinatorlayout.widget.CoordinatorLayout>'''

with open('app/src/main/res/layout/fragment_home.xml', 'w') as f:
    f.write(home_xml)

print("SUCCESS: All missing icons and fragment_home.xml updated cleanly!")
