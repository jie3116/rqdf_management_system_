import '../../../../core/network/api_client.dart';
import '../models/majlis_dashboard_model.dart';

class MajlisDashboardService {
  MajlisDashboardService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<MajlisDashboardModel> fetchDashboard() async {
    final data = await _apiClient.get('/majlis/dashboard');
    return MajlisDashboardModel.fromJson(data);
  }

  Future<Map<String, dynamic>> fetchAnnouncements({bool markAsRead = false}) {
    final suffix = markAsRead ? '?scope=all&mark_as_read=1' : '?scope=all';
    return _apiClient.get('/majlis/announcements$suffix');
  }
}
