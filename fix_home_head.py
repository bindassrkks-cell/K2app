with open('app/src/main/res/layout/fragment_home.xml', 'r') as f:
    text = f.read()

target = """        <com.google.android.material.appbar.MaterialToolbar
            android:id="@+id/home_toolbar"
            android:layout_width="match_parent"
            app:layout_scrollFlags="scroll|enterAlways"
            android:layout_height="?attr/actionBarSize">
        </com.google.android.material.appbar.MaterialToolbar>"""

replacement = """        <com.google.android.material.appbar.MaterialToolbar
            android:id="@+id/home_toolbar"
            android:layout_width="match_parent"
            app:layout_scrollFlags="scroll|enterAlways"
            android:layout_height="?attr/actionBarSize">
            
            <LinearLayout
                android:layout_width="wrap_content"
                android:layout_height="wrap_content"
                android:layout_gravity="center"
                android:orientation="horizontal">
                
                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="Kupido2"
                    android:textColor="@color/home_title_text_color"
                    android:textSize="22sp"
                    android:textStyle="bold"
                    android:fontFamily="sans-serif" />
                
                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="Beta"
                    android:textColor="@color/home_beta_text_color"
                    android:textSize="12sp"
                    android:textStyle="bold"
                    android:layout_marginStart="4dp"
                    android:layout_gravity="top"
                    android:layout_marginTop="2dp"
                    android:fontFamily="sans-serif" />
            </LinearLayout>
        </com.google.android.material.appbar.MaterialToolbar>"""

if target in text:
    text = text.replace(target, replacement)
    with open('app/src/main/res/layout/fragment_home.xml', 'w') as f:
        f.write(text)
    print("Replaced!")
else:
    print("Target not found!")
