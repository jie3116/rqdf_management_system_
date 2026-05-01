import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exception.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/user_model.dart';
import '../../data/repositories/auth_repository.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider({
    required AuthRepository authRepository,
    required ApiClient apiClient,
  })  : _authRepository = authRepository,
        _apiClient = apiClient {
    _apiClient.setUnauthorizedRecovery(_recoverUnauthorized);
  }

  final AuthRepository _authRepository;
  final ApiClient _apiClient;

  ViewState state = ViewState.initial;
  UserModel? currentUser;
  String? errorMessage;
  bool rememberMe = false;

  bool get isAuthenticated => currentUser != null;
  bool _initialized = false;
  bool _pushInitialized = false;
  StreamSubscription<String>? _tokenRefreshSubscription;
  String? _lastSyncedPushToken;

  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;
    await _ensurePushInitialized();
    state = ViewState.loading;
    notifyListeners();
    rememberMe = await _authRepository.loadRememberMe();

    final hasSession = await _authRepository.hasSavedSession();
    if (!hasSession) {
      state = ViewState.success;
      notifyListeners();
      return;
    }

    try {
      currentUser = await _authRepository.me();
      await _syncPushToken();
      errorMessage = null;
      state = ViewState.success;
    } catch (_) {
      final refreshed = await _authRepository.tryRefreshToken();
      if (refreshed) {
        try {
          currentUser = await _authRepository.me();
          await _syncPushToken();
          errorMessage = null;
          state = ViewState.success;
          notifyListeners();
          return;
        } catch (_) {
          await _authRepository.logout();
        }
      }
      currentUser = null;
      state = ViewState.success;
    }
    notifyListeners();
  }

  Future<bool> login({
    required String identifier,
    required String password,
    required bool rememberMeChoice,
  }) async {
    state = ViewState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      currentUser = await _authRepository.login(
        identifier: identifier,
        password: password,
        rememberMe: rememberMeChoice,
      );
      await _syncPushToken();
      rememberMe = rememberMeChoice;
      state = ViewState.success;
      notifyListeners();
      return true;
    } on ApiException catch (error) {
      currentUser = null;
      state = ViewState.error;
      errorMessage = _toUiError(error);
      notifyListeners();
      return false;
    } catch (_) {
      currentUser = null;
      state = ViewState.error;
      errorMessage = 'Username atau password salah';
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await _deactivatePushToken();
    await _authRepository.logout();
    currentUser = null;
    state = ViewState.success;
    errorMessage = null;
    notifyListeners();
  }

  void updateRememberMe(bool value) {
    rememberMe = value;
    notifyListeners();
  }

  Future<bool> _recoverUnauthorized() async {
    final refreshed = await _authRepository.tryRefreshToken();
    if (!refreshed) {
      await logout();
    } else {
      await _syncPushToken();
    }
    return refreshed;
  }

  String _toUiError(ApiException error) {
    if (error.message.trim().isNotEmpty) {
      return error.message;
    }
    return 'Username atau password salah';
  }

  @override
  void dispose() {
    _tokenRefreshSubscription?.cancel();
    super.dispose();
  }

  Future<void> _ensurePushInitialized() async {
    if (_pushInitialized) return;

    try {
      await Firebase.initializeApp();
    } catch (_) {
      return;
    }

    _pushInitialized = true;
    try {
      await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
    } catch (_) {
      // Permission request can fail on unsupported environments.
    }

    _tokenRefreshSubscription ??=
        FirebaseMessaging.instance.onTokenRefresh.listen((token) {
      _lastSyncedPushToken = null;
      unawaited(_syncPushToken(forcedToken: token));
    });
  }

  Future<void> _syncPushToken({String? forcedToken}) async {
    if (currentUser == null) return;
    await _ensurePushInitialized();
    if (!_pushInitialized) return;

    final token = (forcedToken ?? await FirebaseMessaging.instance.getToken())
        ?.trim();
    if (token == null || token.isEmpty) return;
    if (_lastSyncedPushToken == token) return;

    try {
      await _authRepository.registerPushToken(
        token: token,
        platform: _platformLabel(),
      );
      _lastSyncedPushToken = token;
    } catch (_) {
      // Keep auth flow unaffected when push token sync fails.
    }
  }

  Future<void> _deactivatePushToken() async {
    await _ensurePushInitialized();
    if (!_pushInitialized) return;

    final token = (await FirebaseMessaging.instance.getToken())?.trim();
    if (token == null || token.isEmpty) return;

    try {
      await _authRepository.unregisterPushToken(token);
    } catch (_) {
      // Ignore push token deactivation failures.
    } finally {
      if (_lastSyncedPushToken == token) {
        _lastSyncedPushToken = null;
      }
    }
  }

  String _platformLabel() {
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'android';
    }
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return 'ios';
    }
    if (defaultTargetPlatform == TargetPlatform.macOS) {
      return 'macos';
    }
    if (defaultTargetPlatform == TargetPlatform.windows) {
      return 'windows';
    }
    if (defaultTargetPlatform == TargetPlatform.linux) {
      return 'linux';
    }
    return 'unknown';
  }
}
