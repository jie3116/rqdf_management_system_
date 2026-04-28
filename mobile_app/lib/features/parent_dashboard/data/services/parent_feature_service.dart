import '../../../../core/network/api_client.dart';

class ParentFeatureService {
  ParentFeatureService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  static const Map<String, String> _pathByKey = {
    'pengumuman': '/announcements',
    'keuangan': '/finance',
    'tahfidz': '/memorization-report',
    'jadwal': '/weekly-schedule',
    'nilai': '/academic-grades',
    'absensi': '/attendance',
    'perilaku': '/behavior',
  };

  Future<Map<String, dynamic>> fetchFeature({
    required String key,
    int? childId,
    Map<String, dynamic>? query,
  }) async {
    final suffixPath = _pathByKey[key.toLowerCase()];
    if (suffixPath == null) {
      return <String, dynamic>{
        'message': 'Endpoint untuk fitur "$key" belum diatur.',
      };
    }
    if (childId == null || childId <= 0) {
      return <String, dynamic>{
        'message': 'Pilih data anak terlebih dahulu.',
      };
    }
    final endpoint = '/parent/children/$childId$suffixPath${_buildQuery(query)}';
    return _apiClient.get(endpoint);
  }

  String _buildQuery(Map<String, dynamic>? query) {
    if (query == null || query.isEmpty) return '';
    final entries = query.entries.where((entry) {
      final value = entry.value;
      if (value == null) return false;
      if (value is String) return value.trim().isNotEmpty;
      return true;
    }).map((entry) {
      return '${entry.key}=${Uri.encodeQueryComponent('${entry.value}')}';
    }).toList();
    if (entries.isEmpty) return '';
    return '?${entries.join('&')}';
  }
}
