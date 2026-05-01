import '../../../../core/network/api_client.dart';
import '../models/login_response.dart';
import '../models/user_model.dart';

class AuthService {
  AuthService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<LoginResponse> login({
    required String identifier,
    required String password,
  }) async {
    final data = await _apiClient.post(
      '/auth/login',
      withAuth: false,
      body: {
        'identifier': identifier,
        'login_id': identifier,
        'password': password,
      },
    );
    return LoginResponse.fromJson(data);
  }

  Future<UserModel> me() async {
    final data = await _apiClient.get('/auth/me');
    final wrappedUser = data['user'];
    if (wrappedUser is Map<String, dynamic>) {
      return UserModel.fromJson(wrappedUser);
    }
    return UserModel.fromJson(data);
  }

  Future<LoginResponse> refresh(String refreshToken) async {
    final data = await _apiClient.post(
      '/auth/refresh',
      withAuth: false,
      retryOnUnauthorized: false,
      body: {'refresh_token': refreshToken},
    );
    return LoginResponse.fromJson(data);
  }

  Future<void> logout(String refreshToken) async {
    await _apiClient.post(
      '/auth/logout',
      body: {'refresh_token': refreshToken},
      retryOnUnauthorized: false,
    );
  }

  Future<void> syncPushToken({
    required String token,
    required bool isActive,
    String platform = 'unknown',
    String? deviceName,
    String? appVersion,
  }) async {
    await _apiClient.post(
      '/auth/push-token',
      body: {
        'token': token,
        'is_active': isActive,
        'platform': platform,
        if ((deviceName ?? '').trim().isNotEmpty) 'device_name': deviceName,
        if ((appVersion ?? '').trim().isNotEmpty) 'app_version': appVersion,
      },
    );
  }
}
