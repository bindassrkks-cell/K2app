import re

with open('app/build.gradle', 'r') as f:
    text = f.read()

if "lottie" not in text:
    text = text.replace('dependencies {', 'dependencies {\n    implementation("com.airbnb.android:lottie:6.3.0")')
    with open('app/build.gradle', 'w') as f:
        f.write(text)
    print("Added Lottie")
