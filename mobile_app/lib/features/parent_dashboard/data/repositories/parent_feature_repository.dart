import '../models/quick_action_model.dart';
import '../models/quick_action_result_model.dart';
import '../services/parent_feature_service.dart';

class ParentFeatureRepository {
  ParentFeatureRepository(this._service);

  final ParentFeatureService _service;

  Future<QuickActionResultModel> fetchQuickActionData({
    required QuickActionModel action,
    int? childId,
    Map<String, dynamic>? query,
  }) async {
    final payload = await _service.fetchFeature(
      key: action.key,
      childId: childId,
      query: query,
    );
    return QuickActionResultModel(
      key: action.key,
      label: action.label,
      payload: payload,
    );
  }

  Future<Map<String, dynamic>> setSavingsPin({
    required int childId,
    required String pin,
    required String pinConfirm,
  }) {
    return _service.setSavingsPin(
      childId: childId,
      pin: pin,
      pinConfirm: pinConfirm,
    );
  }

  Future<Map<String, dynamic>> submitSavingsTopup({
    required int childId,
    required int amount,
    String? notes,
    required String proofImagePath,
  }) {
    return _service.submitSavingsTopup(
      childId: childId,
      amount: amount,
      notes: notes,
      proofImagePath: proofImagePath,
    );
  }
}
