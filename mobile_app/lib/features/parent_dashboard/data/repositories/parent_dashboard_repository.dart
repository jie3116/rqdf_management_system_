import '../models/parent_dashboard_model.dart';
import '../services/parent_dashboard_service.dart';

class ParentDashboardRepository {
  ParentDashboardRepository(this._service);

  final ParentDashboardService _service;

  Future<ParentDashboardModel> getDashboard({int? studentId}) =>
      _service.fetchDashboard(studentId: studentId);
}
