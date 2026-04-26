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
    final endpoint = '/parent/children/$childId$suffixPath';
    return _apiClient.get(endpoint);
  }
}
