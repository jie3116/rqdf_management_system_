import 'package:shared_preferences/shared_preferences.dart';

class LocalPreferencesStorage {
  static const String _rememberMeKey = 'rqdf_remember_me';

  Future<void> saveRememberMe(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_rememberMeKey, value);
  }

  Future<bool> readRememberMe() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_rememberMeKey) ?? false;
  }
}
