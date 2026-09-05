import re

with open('app/src/main/res/layout/fragment_more.xml', 'r') as f:
    xml = f.read()

# Let's verify if about_app is really there. If not, add it.
if "android:id=\"@+id/about_app\"" not in xml:
    about_xml = """
                <TextView
                    android:id="@+id/about_app"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:drawablePadding="35dp"
                    android:textSize="16sp"
                    android:paddingVertical="15dp"
                    android:text="About App"
                    android:textStyle="bold"
                    android:clickable="true"
                    android:focusable="true"
                    android:background="?android:attr/selectableItemBackground"
                    android:paddingHorizontal="15dp"
                    app:drawableStartCompat="@drawable/ic_info" />
"""
    xml = xml.replace('</LinearLayout>', about_xml + '\\n            </LinearLayout>', 1)
    with open('app/src/main/res/layout/fragment_more.xml', 'w') as f:
        f.write(xml)

