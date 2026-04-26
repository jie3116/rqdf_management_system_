import '../models/majlis_dashboard_model.dart';
import '../services/majlis_dashboard_service.dart';

class MajlisDashboardRepository {
  MajlisDashboardRepository(this._service);

  final MajlisDashboardService _service;

  Future<MajlisDashboardModel> getDashboard() => _service.fetchDashboard();

  Future<Map<String, dynamic>> getAnnouncements({bool markAsRead = false}) {
    return _service.fetchAnnouncements(markAsRead: markAsRead);
  }
}
