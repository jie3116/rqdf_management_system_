import 'package:flutter/foundation.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/quick_action_model.dart';
import '../../data/models/quick_action_result_model.dart';
import '../../data/repositories/parent_feature_repository.dart';

class QuickActionProvider extends ChangeNotifier {
  QuickActionProvider({
    required ParentFeatureRepository repository,
  }) : _repository = repository;

  final ParentFeatureRepository _repository;

  ViewState state = ViewState.initial;
  QuickActionResultModel? result;
  String? errorMessage;

  Future<void> load({
    required QuickActionModel action,
    int? childId,
    Map<String, dynamic>? query,
  }) async {
    state = ViewState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      result = await _repository.fetchQuickActionData(
        action: action,
        childId: childId,
        query: query,
      );
      state = ViewState.success;
    } on ApiException catch (error) {
      state = ViewState.error;
      errorMessage = error.message;
    } catch (_) {
      state = ViewState.error;
      errorMessage = 'Gagal memuat data ${action.label}.';
    }
    notifyListeners();
  }
}
