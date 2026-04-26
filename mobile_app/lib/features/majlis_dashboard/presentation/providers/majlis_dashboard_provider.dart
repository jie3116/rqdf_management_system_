import 'package:flutter/foundation.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../core/utils/json_helper.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/majlis_dashboard_model.dart';
import '../../data/repositories/majlis_dashboard_repository.dart';

class MajlisDashboardProvider extends ChangeNotifier {
  MajlisDashboardProvider({required MajlisDashboardRepository repository})
      : _repository = repository;

  final MajlisDashboardRepository _repository;

  ViewState state = ViewState.initial;
  MajlisDashboardModel? dashboard;
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
      errorMessage = 'Data dashboard majelis gagal dimuat.';
    }
    notifyListeners();
  }

  Future<void> markAnnouncementsRead() async {
    final current = dashboard;
    if (!_isAuthenticated || current == null) return;
    if (current.unreadAnnouncementsCount <= 0) return;
    try {
      final payload = await _repository.getAnnouncements(markAsRead: true);
      final items = JsonHelper.asList(payload['items'])
          .map((item) => MajlisAnnouncement.fromJson(JsonHelper.asMap(item)))
          .toList();
      dashboard = MajlisDashboardModel(
        profile: current.profile,
        summary: current.summary,
        announcements: items,
        unreadAnnouncementsCount: JsonHelper.asInt(payload['unread_count']),
        tahfidzRecords: current.tahfidzRecords,
        recitationRecords: current.recitationRecords,
        evaluationRecords: current.evaluationRecords,
        attendance: current.attendance,
        scheduleDays: current.scheduleDays,
        finance: current.finance,
      );
      notifyListeners();
    } catch (_) {
      // Keep UI usable even if mark-as-read request fails.
    }
  }
}
