import 'package:flutter/foundation.dart';

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

  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;
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
      errorMessage = null;
      state = ViewState.success;
    } catch (_) {
      final refreshed = await _authRepository.tryRefreshToken();
      if (refreshed) {
        try {
          currentUser = await _authRepository.me();
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
    }
    return refreshed;
  }

  String _toUiError(ApiException error) {
    if (error.message.trim().isNotEmpty) {
      return error.message;
    }
    return 'Username atau password salah';
  }
}
