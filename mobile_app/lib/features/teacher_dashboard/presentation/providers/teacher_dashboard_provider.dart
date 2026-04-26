import 'package:flutter/foundation.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/teacher_dashboard_model.dart';
import '../../data/repositories/teacher_dashboard_repository.dart';

class TeacherDashboardProvider extends ChangeNotifier {
  TeacherDashboardProvider({required TeacherDashboardRepository repository})
      : _repository = repository;

  final TeacherDashboardRepository _repository;

  ViewState state = ViewState.initial;
  TeacherDashboardModel? dashboard;
  String? errorMessage;
  bool _isAuthenticated = false;

  void setSession({required bool isAuthenticated}) {
    _isAuthenticated = isAuthenticated;
    if (!isAuthenticated) {
      state = ViewState.initial;
      dashboard = null;
      errorMessage = null;
      notifyListeners();
    }
  }

  Future<void> fetchDashboard({bool forceRefresh = false}) async {
    if (!_isAuthenticated) return;
    if (!forceRefresh && state == ViewState.success && dashboard != null) {
      return;
    }

    state = ViewState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      dashboard = await _repository.getDashboard();
      state = ViewState.success;
    } on ApiException catch (error) {
      state = ViewState.error;
      errorMessage = error.message;
    } catch (_) {
      state = ViewState.error;
      errorMessage = 'Data dashboard guru gagal dimuat.';
    }
    notifyListeners();
  }
}
