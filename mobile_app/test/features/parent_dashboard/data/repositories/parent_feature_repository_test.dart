import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:rq_mobile/features/parent_dashboard/data/models/quick_action_model.dart';
import 'package:rq_mobile/features/parent_dashboard/data/repositories/parent_feature_repository.dart';
import 'package:rq_mobile/features/parent_dashboard/data/services/parent_feature_service.dart';

class _MockParentFeatureService extends Mock implements ParentFeatureService {}

void main() {
  late _MockParentFeatureService service;
  late ParentFeatureRepository repository;

  setUp(() {
    service = _MockParentFeatureService();
    repository = ParentFeatureRepository(service);
  });

  test('fetchQuickActionData returns payload from service', () async {
    const action = QuickActionModel(key: 'keuangan', label: 'Keuangan');
    when(
      () => service.fetchFeature(
        key: action.key,
        childId: 10,
      ),
    ).thenAnswer(
      (_) async => <String, dynamic>{'billing_total': 100000},
    );

    final result = await repository.fetchQuickActionData(
      action: action,
      childId: 10,
    );

    expect(result.key, 'keuangan');
    expect(result.label, 'Keuangan');
    expect(result.payload['billing_total'], 100000);
    verify(
      () => service.fetchFeature(
        key: action.key,
        childId: 10,
      ),
    ).called(1);
  });
}
