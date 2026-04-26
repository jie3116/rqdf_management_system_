import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import 'package:rq_mobile/core/network/api_client.dart';
import 'package:rq_mobile/core/storage/secure_token_storage.dart';

class _MockHttpClient extends Mock implements http.Client {}

class _MockTokenStorage extends Mock implements SecureTokenStorage {}

void main() {
  late _MockHttpClient httpClient;
  late _MockTokenStorage tokenStorage;
  late ApiClient apiClient;
  String currentToken = 'old_token';

  setUpAll(() {
    registerFallbackValue(Uri.parse('https://fallback'));
    registerFallbackValue(<String, String>{});
  });

  setUp(() {
    httpClient = _MockHttpClient();
    tokenStorage = _MockTokenStorage();
    currentToken = 'old_token';

    when(() => tokenStorage.readAccessToken())
        .thenAnswer((_) async => currentToken);

    when(
      () => httpClient.get(
        any(),
        headers: any(named: 'headers'),
      ),
    ).thenAnswer((invocation) async {
      final headers =
          invocation.namedArguments[#headers] as Map<String, String>? ??
              <String, String>{};
      final authHeader = headers['Authorization'] ?? '';
      if (authHeader == 'Bearer old_token') {
        return http.Response(
            '{"success":false,"message":"invalid_or_expired_token"}', 401);
      }
      return http.Response(
        jsonEncode(<String, dynamic>{
          'success': true,
          'data': <String, dynamic>{'ok': true},
        }),
        200,
      );
    });

    apiClient = ApiClient(
      tokenStorage: tokenStorage,
      httpClient: httpClient,
    );
  });

  test(
      'single-flight unauthorized recovery should run only once for parallel 401',
      () async {
    var recoveryCalled = 0;
    apiClient.setUnauthorizedRecovery(() async {
      recoveryCalled += 1;
      await Future<void>.delayed(const Duration(milliseconds: 40));
      currentToken = 'new_token';
      return true;
    });

    final results = await Future.wait([
      apiClient.get('/parent/children/1/finance'),
      apiClient.get('/parent/children/1/attendance'),
    ]);

    expect(results.length, 2);
    expect(results[0]['ok'], true);
    expect(results[1]['ok'], true);
    expect(recoveryCalled, 1);
  });
}
