import '../../../../core/storage/local_preferences.dart';
import '../../../../core/storage/secure_token_storage.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';

class AuthRepository {
  AuthRepository({
    required AuthService authService,
    required SecureTokenStorage tokenStorage,
    required LocalPreferencesStorage preferencesStorage,
  })  : _authService = authService,
        _tokenStorage = tokenStorage,
        _preferencesStorage = preferencesStorage;

  final AuthService _authService;
  final SecureTokenStorage _tokenStorage;
  final LocalPreferencesStorage _preferencesStorage;

  Future<UserModel> login({
    required String identifier,
    required String password,
    required bool rememberMe,
  }) async {
    final response = await _authService.login(
      identifier: identifier,
      password: password,
    );
    await _tokenStorage.saveTokens(
      accessToken: response.tokens.accessToken,
      refreshToken: response.tokens.refreshToken,
    );
    await _preferencesStorage.saveRememberMe(rememberMe);
    if (response.user.id > 0) {
      return response.user;
    }
    return _authService.me();
  }

  Future<UserModel> me() => _authService.me();

  Future<bool> hasSavedSession() async {
    final token = await _tokenStorage.readAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<bool> tryRefreshToken() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) {
      return false;
    }
    try {
      final refreshed = await _authService.refresh(refreshToken);
      await _tokenStorage.saveTokens(
        accessToken: refreshed.tokens.accessToken,
        refreshToken: refreshed.tokens.refreshToken,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> loadRememberMe() => _preferencesStorage.readRememberMe();

  Future<void> logout() async {
    final refreshToken = await _tokenStorage.readRefreshToken() ?? '';
    try {
      await _authService.logout(refreshToken);
    } catch (_) {
      // Keep local logout even when API session is already invalid.
    }
    await _tokenStorage.clearTokens();
  }
}
