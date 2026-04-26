import '../models/teacher_dashboard_model.dart';
import '../services/teacher_dashboard_service.dart';

class TeacherDashboardRepository {
  TeacherDashboardRepository(this._service);

  final TeacherDashboardService _service;

  Future<TeacherDashboardModel> getDashboard() => _service.fetchDashboard();
}
