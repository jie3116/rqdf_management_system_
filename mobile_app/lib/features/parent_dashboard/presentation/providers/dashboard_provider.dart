import 'package:flutter/foundation.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/child_model.dart';
import '../../data/models/parent_dashboard_model.dart';
import '../../data/repositories/parent_dashboard_repository.dart';

class DashboardProvider extends ChangeNotifier {
  DashboardProvider({required ParentDashboardRepository dashboardRepository})
      : _dashboardRepository = dashboardRepository;

  final ParentDashboardRepository _dashboardRepository;

  ViewState state = ViewState.initial;
  ParentDashboardModel? dashboard;
  String? errorMessage;
  int selectedBottomNavIndex = 0;
  int? selectedChildId;
  bool _isAuthenticated = false;
  String? _userName;

  bool get hasDashboard => dashboard != null;
  String get greetingName => dashboard?.guardianName.isNotEmpty == true
      ? dashboard!.guardianName
      : (_userName?.isNotEmpty == true ? _userName! : '-');

  ChildModel? get selectedChild {
    if (dashboard == null) return null;
    if (selectedChildId == null) return dashboard!.selectedChild;
    return dashboard!.children
            .where((child) => child.id == selectedChildId)
            .firstOrNull ??
        dashboard!.selectedChild;
  }

  void setSession({
    required bool isAuthenticated,
    required String? userName,
  }) {
    _isAuthenticated = isAuthenticated;
    _userName = userName;
    if (!isAuthenticated) {
      dashboard = null;
      state = ViewState.initial;
      errorMessage = null;
      selectedBottomNavIndex = 0;
      selectedChildId = null;
      notifyListeners();
    }
  }

  Future<void> fetchDashboard({
    bool forceRefresh = false,
    int? studentId,
  }) async {
    if (!_isAuthenticated) return;
    final requestedStudentId = studentId ?? selectedChildId;
    if (!forceRefresh &&
        state == ViewState.success &&
        dashboard != null &&
        requestedStudentId == selectedChildId) {
      return;
    }

    state = ViewState.loading;
    errorMessage = null;
    notifyListeners();
    try {
      final result =
          await _dashboardRepository.getDashboard(studentId: requestedStudentId);
      dashboard = result;
      selectedChildId = result.selectedChild?.id;
      state = ViewState.success;
    } on ApiException catch (error) {
      state = ViewState.error;
      errorMessage = error.message;
    } catch (_) {
      state = ViewState.error;
      errorMessage = 'Data dashboard gagal dimuat.';
    }
    notifyListeners();
  }

  void setBottomNav(int index) {
    selectedBottomNavIndex = index;
    notifyListeners();
  }

  Future<void> selectChild(ChildModel child) async {
    selectedChildId = child.id;
    notifyListeners();
    await fetchDashboard(forceRefresh: true, studentId: child.id);
  }
}

extension _IterableExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
