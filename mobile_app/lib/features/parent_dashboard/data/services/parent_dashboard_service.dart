import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exception.dart';
import '../../../../core/utils/json_helper.dart';
import '../models/parent_dashboard_model.dart';

class ParentDashboardService {
  ParentDashboardService({required ApiClient apiClient})
      : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<ParentDashboardModel> fetchDashboard({int? studentId}) async {
    try {
      final suffix = studentId != null ? '?student_id=$studentId' : '';
      final data = await _apiClient.get('/parent/dashboard$suffix');
      return ParentDashboardModel.fromJson(data);
    } on ApiException catch (error) {
      final isNotFound = error.statusCode == 404 ||
          error.code == 'not_found' ||
          error.message.toLowerCase() == 'not_found';
      if (!isNotFound) rethrow;

      // Fallback untuk backend yang belum menyediakan /parent/dashboard
      // namun sudah menyediakan /parent/children.
      final childrenPayload = await _apiClient.get('/parent/children');
      final children = JsonHelper.asList(childrenPayload['children']);
      final parent = JsonHelper.asMap(childrenPayload['parent']);
      final selectedChild = children.isNotEmpty
          ? JsonHelper.asMap(children.first)
          : <String, dynamic>{};

      final mapped = <String, dynamic>{
        'guardian_name': JsonHelper.asString(parent['full_name'], fallback: '-'),
        'children': children,
        'selected_child': selectedChild,
        'summary': <String, dynamic>{},
        'quick_actions': <dynamic>[],
        'recent_activities': <dynamic>[],
        'announcements': <dynamic>[],
        'unread_announcements_count': 0,
      };
      return ParentDashboardModel.fromJson(mapped);
    }
  }
}
