import '../../../../core/utils/json_helper.dart';

class AuthTokens {
  AuthTokens({
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'Bearer',
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;

  bool get hasAccessToken => accessToken.isNotEmpty;
  bool get hasRefreshToken => refreshToken.isNotEmpty;

  factory AuthTokens.fromJson(Map<String, dynamic> json) {
    return AuthTokens(
      accessToken: JsonHelper.asString(
        json['access_token'] ?? json['token'] ?? json['accessToken'],
      ),
      refreshToken: JsonHelper.asString(
        json['refresh_token'] ?? json['refreshToken'],
      ),
      tokenType: JsonHelper.asString(
        json['token_type'],
        fallback: 'Bearer',
      ),
    );
  }
}
