import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../constants/app_constants.dart';
import '../storage/secure_token_storage.dart';
import 'api_exception.dart';
import 'api_response_parser.dart';

typedef UnauthorizedRecovery = Future<bool> Function();

class ApiClient {
  ApiClient({
    required SecureTokenStorage tokenStorage,
    http.Client? httpClient,
  })  : _tokenStorage = tokenStorage,
        _httpClient = httpClient ?? http.Client();

  final SecureTokenStorage _tokenStorage;
  final http.Client _httpClient;
  final Duration _timeout = const Duration(seconds: 18);
  UnauthorizedRecovery? _unauthorizedRecovery;
  Future<bool>? _ongoingRecovery;

  void setUnauthorizedRecovery(UnauthorizedRecovery? callback) {
    _unauthorizedRecovery = callback;
  }

  Future<Map<String, dynamic>> get(
    String path, {
    bool withAuth = true,
    bool retryOnUnauthorized = true,
  }) {
    return _request(
      method: 'GET',
      path: path,
      withAuth: withAuth,
      retryOnUnauthorized: retryOnUnauthorized,
    );
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
    bool withAuth = true,
    bool retryOnUnauthorized = true,
  }) {
    return _request(
      method: 'POST',
      path: path,
      body: body,
      withAuth: withAuth,
      retryOnUnauthorized: retryOnUnauthorized,
    );
  }

  Future<Map<String, dynamic>> _request({
    required String method,
    required String path,
    Map<String, dynamic>? body,
    required bool withAuth,
    required bool retryOnUnauthorized,
  }) async {
    final uri = Uri.parse('${AppConstants.baseUrl}$path');
    final headers = await _buildHeaders(withAuth: withAuth);

    http.Response response;
    try {
      if (method == 'GET') {
        response =
            await _httpClient.get(uri, headers: headers).timeout(_timeout);
      } else {
        response = await _httpClient
            .post(
              uri,
              headers: headers,
              body: jsonEncode(body ?? <String, dynamic>{}),
            )
            .timeout(_timeout);
      }
    } on TimeoutException {
      throw ApiException(message: 'Koneksi timeout. Coba beberapa saat lagi.');
    } on SocketException {
      throw ApiException(message: 'Tidak ada koneksi internet.');
    }

    final parsedPayload = _tryDecode(response.body);
    final successFlag = parsedPayload['success'];
    if (response.statusCode == 401 &&
        withAuth &&
        retryOnUnauthorized &&
        _unauthorizedRecovery != null) {
      final recovered = await _recoverUnauthorizedSingleFlight();
      if (recovered) {
        return _request(
          method: method,
          path: path,
          body: body,
          withAuth: withAuth,
          retryOnUnauthorized: false,
        );
      }
    }

    if (response.statusCode >= 500) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Server sedang bermasalah. Silakan coba lagi.',
      );
    }

    final isWrappedApi = parsedPayload.containsKey('success');
    if (isWrappedApi && successFlag != true) {
      throw ApiException(
        statusCode: response.statusCode,
        code: parsedPayload['code']?.toString(),
        message: ApiResponseParser.extractMessage(parsedPayload),
      );
    }

    if (!isWrappedApi && response.statusCode >= 400) {
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Permintaan gagal (${response.statusCode}).',
      );
    }

    return isWrappedApi
        ? ApiResponseParser.extractData(parsedPayload)
        : parsedPayload;
  }

  Future<bool> _recoverUnauthorizedSingleFlight() async {
    final runningRecovery = _ongoingRecovery;
    if (runningRecovery != null) {
      return runningRecovery;
    }

    final recoveryFuture = _runRecovery();
    _ongoingRecovery = recoveryFuture;
    try {
      return await recoveryFuture;
    } finally {
      if (identical(_ongoingRecovery, recoveryFuture)) {
        _ongoingRecovery = null;
      }
    }
  }

  Future<bool> _runRecovery() async {
    try {
      return await _unauthorizedRecovery!.call();
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, String>> _buildHeaders({required bool withAuth}) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (withAuth) {
      final token = await _tokenStorage.readAccessToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    return headers;
  }

  Map<String, dynamic> _tryDecode(String raw) {
    if (raw.isEmpty) {
      return <String, dynamic>{};
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {
      return <String, dynamic>{};
    }
    return <String, dynamic>{};
  }
}
