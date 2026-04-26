class ApiException implements Exception {
  ApiException({
    required this.message,
    this.statusCode,
    this.code,
  });

  final String message;
  final int? statusCode;
  final String? code;

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() =>
      'ApiException(statusCode: $statusCode, message: $message, code: $code)';
}
