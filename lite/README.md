# K2App Lite

K2App Lite is a standalone Android application module (`:lite`) with its own application ID (`com.k2app.lite`) and a separate APK workflow. It does not depend on the main K2App application module, downloader engine, or its large native libraries.

The app uses the existing public K2App service at `https://k2app-telegram-bot.onrender.com`. Pair once by sending `/pair` to the K2App Telegram bot and entering its one-use code in Settings. The bearer token is encrypted with Android Keystore and is not embedded in the APK. Pairing is valid for 90 days; pair again after expiry or a server reset.

Link analysis returns the available choices from the server. Selecting one creates a job and the server delivers the media to the paired Telegram chat. K2 Lite displays the job progress and completed history; it does not download or retain a second copy of the media on the phone. The service currently allows only the configured Telegram owner to use paired Lite API tokens, and its worker processes one media job at a time.

Build the debug APK locally with:

```sh
./gradlew :lite:assembleDebug
```

The resulting installable APK is written to `lite/build/outputs/apk/debug/lite-debug.apk`. The dedicated GitHub Actions workflow builds only this module and publishes the APK as the `K2App-Lite-debug` artifact.
