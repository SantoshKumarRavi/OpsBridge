# Flutter analytics microfrontend

Independent Flutter field/operations view over the Strawberry GraphQL BFF. It demonstrates a mobile UI using Dart, Material 3, responsive layout, secure token storage, OIDC authorization-code login with PKCE through AppAuth, and refresh-token rotation before expiry. The BFF forwards the user credential to the authoritative gateway and does not introduce another case database or decision engine.

Run with Flutter installed:

```sh
cd apps/flutter-analytics
flutter pub get
flutter analyze --fatal-infos
flutter test
flutter build apk --debug
flutter run --dart-define=OPSBRIDGE_GRAPHQL_URL=http://10.0.2.2:8010/graphql
```

The app uses the standalone `material_ui` package and requires Flutter 3.50 or newer. Linux/WSL checks pass dependency resolution, formatting, analysis, and two widget tests for the case summary and API failure state. `flutter build apk --debug` also passes locally and produces `build/app/outputs/flutter-apk/app-debug.apk`. Android/iOS runner projects are generated, and the AppAuth callback scheme is configured for `opsbridgeflutter://oauth2redirect`. CI is configured to build an Android debug APK; its hosted run is pending. iOS build/signing and OIDC login on a device remain unverified because Xcode and device credentials are unavailable in WSL.

For OIDC, add `--dart-define=OPSBRIDGE_OIDC_ISSUER=http://10.0.2.2:8081/realms/opsbridge` and register the `opsbridgeflutter://oauth2redirect` redirect for the `opsbridge-flutter` public Keycloak client. `10.0.2.2` is for the Android emulator; use a host-reachable URL for iOS simulator/device runs and HTTPS outside local development. Without an issuer, the app uses the local development identity header; never use that path in production.
