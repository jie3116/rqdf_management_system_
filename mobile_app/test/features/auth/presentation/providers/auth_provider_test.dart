import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:rq_mobile/core/network/api_client.dart';
import 'package:rq_mobile/core/network/api_exception.dart';
import 'package:rq_mobile/features/auth/data/models/user_model.dart';
import 'package:rq_mobile/features/auth/data/repositories/auth_repository.dart';
import 'package:rq_mobile/features/auth/presentation/providers/auth_provider.dart';
import 'package:rq_mobile/shared/models/view_state.dart';

class _MockAuthRepository extends Mock implements AuthRepository {}

class _MockApiClient extends Mock implements ApiClient {}

void main() {
  late _MockAuthRepository authRepository;
  late _MockApiClient apiClient;
  late AuthProvider provider;

  setUpAll(() {
    registerFallbackValue(() async => false);
  });

  setUp(() {
    authRepository = _MockAuthRepository();
    apiClient = _MockApiClient();
    when(() => apiClient.setUnauthorizedRecovery(any())).thenReturn(null);
    provider = AuthProvider(
      authRepository: authRepository,
      apiClient: apiClient,
    );
  });

  test('initialize without saved session should be unauthenticated', () async {
    when(() => authRepository.loadRememberMe()).thenAnswer((_) async => false);
    when(() => authRepository.hasSavedSession()).thenAnswer((_) async => false);

    await provider.initialize();

    expect(provider.state, ViewState.success);
    expect(provider.isAuthenticated, isFalse);
  });

  test('login success should set authenticated user', () async {
    final user = UserModel(
      id: 1,
      name: 'Aji',
      username: '08123',
      role: 'WALI_MURID',
    );

    when(
      () => authRepository.login(
        identifier: 'admin',
        password: 'secret',
        rememberMe: true,
      ),
    ).thenAnswer((_) async => user);

    final result = await provider.login(
      identifier: 'admin',
      password: 'secret',
      rememberMeChoice: true,
    );

    expect(result, isTrue);
    expect(provider.currentUser?.name, 'Aji');
    expect(provider.state, ViewState.success);
  });

  test('login failed should expose readable error', () async {
    when(
      () => authRepository.login(
        identifier: 'admin',
        password: 'wrong',
        rememberMe: false,
      ),
    ).thenThrow(
      ApiException(message: 'Username atau password salah'),
    );

    final result = await provider.login(
      identifier: 'admin',
      password: 'wrong',
      rememberMeChoice: false,
    );

    expect(result, isFalse);
    expect(provider.state, ViewState.error);
    expect(provider.errorMessage, isNotNull);
  });
}
