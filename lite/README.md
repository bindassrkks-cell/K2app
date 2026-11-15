# K2App Lite

K2App Lite is a standalone Android application module (`:lite`) with application ID `com.k2app.lite` and its own APK workflow. It is independent of the main K2App Android app. It uses a fixed HTTPS API origin in the build configuration; the APK contains no Telegram bot token, admin key or server secret.

## Device session and privacy

On first use, the app creates a random anonymous device session through `POST /api/v1/auth/session`. The bearer token is encrypted with Android Keystore and is not included in Android backups. No Telegram pairing or Telegram delivery is used by Lite. Each installation has its own server-side identity and can only read or download its own jobs and files.

There is no account or recovery method. If app data is cleared or the app is reinstalled, its session cannot be recovered. **Reset session** revokes that device token and deletes that session’s server-side jobs and files; media already saved on the phone remains.

## Downloads

The app submits a public media URL, shows available formats and asks the server to prepare the selected file. It then uses Android DownloadManager with the session bearer token to save the result under the app’s device Downloads area, where it can be opened from the Lite library. The server returns one final file per job, caps Lite source/result data at 300 MB and expires server-side jobs after six hours. Each session can analyze five links per hour, and the service creates at most 100 new sessions per hour across all devices. The worker processes one media job at a time. Availability still depends on the public source site and formats it exposes.

The anonymous API implementation is included in the K2App Lite review branch. The configured Render service must be updated with that backend code before this APK can create anonymous sessions and serve direct files. The Lite PR is intentionally not merged or deployed by this change.

## Build

```sh
./gradlew :lite:assembleDebug
./gradlew :lite:assembleRelease
```

The installable debug APK is written to `lite/build/outputs/apk/debug/lite-debug.apk`. The dedicated GitHub Actions workflow builds only this module and publishes the APK as the `K2App-Lite-debug` artifact.
