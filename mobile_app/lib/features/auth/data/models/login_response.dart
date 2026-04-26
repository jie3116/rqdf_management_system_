import 'auth_tokens.dart';
import 'user_model.dart';

class LoginResponse {
  LoginResponse({
    required this.tokens,
    required this.user,
  });

  final AuthTokens tokens;
  final UserModel user;

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    final userJson = json['user'] is Map<String, dynamic>
        ? json['user'] as Map<String, dynamic>
        : <String, dynamic>{};
    return LoginResponse(
      tokens: AuthTokens.fromJson(json),
      user: UserModel.fromJson(userJson),
    );
  }
}
