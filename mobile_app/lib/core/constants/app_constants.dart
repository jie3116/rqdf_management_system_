class AppConstants {
  static const String appName = 'RQDF Management System';

  static const String baseUrl = String.fromEnvironment(
    'BASE_URL_API',
    defaultValue: 'https://app.rqdf.co.id/api/v1',
  );
}
