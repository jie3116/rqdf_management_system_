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
    'tabungan': '/savings',
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
    final endpoint =
        '/parent/children/$childId$suffixPath${_buildQuery(query)}';
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

  Future<Map<String, dynamic>> setSavingsPin({
    required int childId,
    required String pin,
    required String pinConfirm,
  }) async {
    final endpoint = '/parent/children/$childId/savings/pin';
    return _apiClient.post(
      endpoint,
      body: <String, dynamic>{
        'pin': pin,
        'pin_confirm': pinConfirm,
      },
    );
  }

  Future<Map<String, dynamic>> submitSavingsTopup({
    required int childId,
    required int amount,
    String? notes,
    required String proofImagePath,
  }) {
    final endpoint = '/parent/children/$childId/savings/topup';
    final normalizedPath = proofImagePath.replaceAll('\\', '/');
    final filename = normalizedPath.split('/').last;
    return _apiClient.postMultipart(
      endpoint,
      fields: <String, String>{
        'amount': '$amount',
        'notes': notes?.trim() ?? '',
      },
      fileField: 'proof_image',
      filePath: proofImagePath,
      fileName: filename,
    );
  }
}
