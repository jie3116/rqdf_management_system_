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
  bool isSubmittingPin = false;
  bool isSubmittingTopup = false;

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

  Future<String?> setSavingsPin({
    required int childId,
    required String pin,
    required String pinConfirm,
  }) async {
    isSubmittingPin = true;
    notifyListeners();
    try {
      await _repository.setSavingsPin(
        childId: childId,
        pin: pin,
        pinConfirm: pinConfirm,
      );
      return null;
    } on ApiException catch (error) {
      return error.message;
    } catch (_) {
      return 'Gagal menyimpan PIN tabungan.';
    } finally {
      isSubmittingPin = false;
      notifyListeners();
    }
  }

  Future<String?> submitSavingsTopup({
    required int childId,
    required int amount,
    String? notes,
    required String proofImagePath,
  }) async {
    isSubmittingTopup = true;
    notifyListeners();
    try {
      await _repository.submitSavingsTopup(
        childId: childId,
        amount: amount,
        notes: notes,
        proofImagePath: proofImagePath,
      );
      return null;
    } on ApiException catch (error) {
      return error.message;
    } catch (_) {
      return 'Gagal mengirim top up tabungan.';
    } finally {
      isSubmittingTopup = false;
      notifyListeners();
    }
  }
}
