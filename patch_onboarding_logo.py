import re

for file_idx in range(1, 4):
    try:
        path = f'app/src/main/res/layout/page_onboarding_{file_idx}.xml'
        with open(path, 'r') as f:
            text = f.read()

        text = re.sub(
            r'<com.airbnb.lottie.LottieAnimationView[^>]+>',
            r'''<ImageView
        android:layout_width="150dp"
        android:layout_height="150dp"
        android:src="@mipmap/ic_launcher"
        android:layout_marginBottom="16dp"/>''',
            text,
            flags=re.DOTALL
        )

        with open(path, 'w') as f:
            f.write(text)
    except Exception:
        pass
