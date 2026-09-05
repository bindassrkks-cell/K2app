import re

with open('app/src/main/res/layout/fragment_home.xml', 'r') as f:
    xml = f.read()

pattern = r'<com\.google\.android\.material\.appbar\.MaterialToolbar[^>]+android:id="@+id/home_toolbar"[^>]+/>'

toolbar_replacement = """        <com.google.android.material.appbar.MaterialToolbar
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
                    android:textColor="#000000"
                    android:textSize="22sp"
                    android:textStyle="bold"
                    android:fontFamily="sans-serif" />
                    
                <TextView
                    android:layout_width="wrap_content"
                    android:layout_height="wrap_content"
                    android:text="Beta"
                    android:textColor="#FF0000"
                    android:textSize="12sp"
                    android:textStyle="bold"
                    android:layout_marginStart="4dp"
                    android:layout_gravity="top"
                    android:layout_marginTop="2dp"
                    android:fontFamily="sans-serif" />
            </LinearLayout>
        </com.google.android.material.appbar.MaterialToolbar>"""

xml = re.sub(pattern, toolbar_replacement, xml, flags=re.DOTALL)

with open('app/src/main/res/layout/fragment_home.xml', 'w') as f:
    f.write(xml)
