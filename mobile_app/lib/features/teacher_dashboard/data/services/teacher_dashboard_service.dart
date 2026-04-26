import '../../../../core/network/api_client.dart';
import '../models/teacher_dashboard_model.dart';

class TeacherDashboardService {
  TeacherDashboardService({required ApiClient apiClient})
      : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<TeacherDashboardModel> fetchDashboard() async {
    final data = await _apiClient.get('/teacher/dashboard');
    return TeacherDashboardModel.fromJson(data);
  }
}
