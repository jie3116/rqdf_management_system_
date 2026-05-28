import 'package:shared_preferences/shared_preferences.dart';

class LocalPreferencesStorage {
  static const String _rememberMeKey = 'rqdf_remember_me';
  static const String _activeRoleKey = 'rqdf_active_role';

  Future<void> saveRememberMe(bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_rememberMeKey, value);
  }

  Future<bool> readRememberMe() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_rememberMeKey) ?? false;
  }

  Future<void> saveActiveRole(String value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_activeRoleKey, value);
  }

  Future<String?> readActiveRole() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_activeRoleKey);
  }

  Future<void> clearActiveRole() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_activeRoleKey);
  }
}
