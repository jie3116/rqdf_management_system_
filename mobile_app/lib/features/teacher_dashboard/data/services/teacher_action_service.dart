import '../../../../core/network/api_client.dart';

class TeacherActionService {
  TeacherActionService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  static const Map<String, String> _pathByKey = {
    'input-grades': '/teacher/input-grades',
    'input-attendance': '/teacher/input-attendance',
    'input-tahfidz': '/teacher/input-tahfidz',
    'input-recitation': '/teacher/input-recitation',
    'input-evaluation': '/teacher/input-evaluation',
    'input-behavior': '/teacher/input-behavior',
    'grade-history': '/teacher/grade-history',
    'attendance-history': '/teacher/attendance-history',
    'homeroom-students': '/teacher/homeroom-students',
    'homeroom-student-detail': '/teacher/homeroom-students',
    'class-announcements': '/teacher/class-announcements',
  };

  Future<Map<String, dynamic>> load({
    required String key,
    Map<String, dynamic>? query,
  }) async {
    final path = _pathByKey[key];
    if (path == null) {
      throw Exception('Teacher action path not found for $key');
    }
    final suffix = _buildQuery(query);
    return _apiClient.get('$path$suffix');
  }

  Future<Map<String, dynamic>> submit({
    required String key,
    required Map<String, dynamic> body,
  }) async {
    final path = _pathByKey[key];
    if (path == null) {
      throw Exception('Teacher action path not found for $key');
    }
    return _apiClient.post(path, body: body);
  }

  String _buildQuery(Map<String, dynamic>? query) {
    if (query == null || query.isEmpty) return '';
    final entries = query.entries
        .where((entry) {
          final value = entry.value;
          if (value == null) return false;
          if (value is String) return value.trim().isNotEmpty;
          return true;
        })
        .map((entry) =>
            '${entry.key}=${Uri.encodeQueryComponent('${entry.value}')}')
        .toList();
    if (entries.isEmpty) return '';
    return '?${entries.join('&')}';
  }
}
