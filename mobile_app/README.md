# RQ Mobile

Flutter client scaffold for the backend in this repository.

## Status

This folder contains the Flutter app code (`lib/` and `pubspec.yaml`).
Because Flutter SDK is not installed in the current environment, native folders (`android/`, `ios/`, etc.) were not generated here.

## First-time setup

1. Install Flutter SDK.
2. Open terminal in `mobile_app/`.
3. Run `flutter create .`
4. Run `flutter pub get`
5. Run `flutter run`

## Backend base URL

Default app URL:

- Android emulator: `http://10.0.2.2:8000/api/v1`

For real device testing, override it with your LAN IP:

```powershell
flutter run --dart-define=BASE_URL_API=http://192.168.1.10:8000/api/v1
```

Notes:

- HP and backend host must be on the same network.
- Backend server must listen on a non-localhost interface, for example `0.0.0.0`.
- `10.0.2.2` only works from the Android emulator, not from a physical phone.
