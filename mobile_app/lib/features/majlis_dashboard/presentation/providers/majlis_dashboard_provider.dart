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
