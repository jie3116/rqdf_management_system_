import '../models/quick_action_model.dart';
import '../models/quick_action_result_model.dart';
import '../services/parent_feature_service.dart';

class ParentFeatureRepository {
  ParentFeatureRepository(this._service);

  final ParentFeatureService _service;

  Future<QuickActionResultModel> fetchQuickActionData({
    required QuickActionModel action,
    int? childId,
  }) async {
    final payload = await _service.fetchFeature(
      key: action.key,
      childId: childId,
    );
    return QuickActionResultModel(
      key: action.key,
      label: action.label,
      payload: payload,
    );
  }
}
