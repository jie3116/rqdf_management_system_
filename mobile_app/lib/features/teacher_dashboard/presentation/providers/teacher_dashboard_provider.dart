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
  int _announcementSignal = 0;
  int _lastAnnouncementDelta = 0;

  int get announcementSignal => _announcementSignal;
  int get lastAnnouncementDelta => _lastAnnouncementDelta;

  void setSession({required bool isAuthenticated}) {
    _isAuthenticated = isAuthenticated;
    if (!isAuthenticated) {
      state = ViewState.initial;
      dashboard = null;
      errorMessage = null;
      _announcementSignal = 0;
      _lastAnnouncementDelta = 0;
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
      final previousUnread = dashboard?.unreadAnnouncementsCount;
      dashboard = await _repository.getDashboard();
      _lastAnnouncementDelta = 0;
      if (previousUnread != null &&
          dashboard!.unreadAnnouncementsCount > previousUnread) {
        _lastAnnouncementDelta =
            dashboard!.unreadAnnouncementsCount - previousUnread;
        _announcementSignal += 1;
      }
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
