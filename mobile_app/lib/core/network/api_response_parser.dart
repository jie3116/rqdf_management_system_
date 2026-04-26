class ApiResponseParser {
  const ApiResponseParser._();

  static Map<String, dynamic> extractData(Map<String, dynamic> json) {
    final hasSuccessFlag = json.containsKey('success');
    if (!hasSuccessFlag) {
      return json;
    }

    if (json['success'] == true) {
      final payload = json['data'];
      return payload is Map<String, dynamic> ? payload : <String, dynamic>{};
    }

    return <String, dynamic>{};
  }

  static String extractMessage(Map<String, dynamic> json) {
    final message = json['message'];
    if (message is String && message.trim().isNotEmpty) {
      return message;
    }
    return 'Terjadi kesalahan pada server.';
  }
}
