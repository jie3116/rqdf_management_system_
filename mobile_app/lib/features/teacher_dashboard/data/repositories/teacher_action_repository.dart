import '../services/teacher_action_service.dart';

class TeacherActionRepository {
  TeacherActionRepository(this._service);

  final TeacherActionService _service;

  Future<Map<String, dynamic>> load({
    required String key,
    Map<String, dynamic>? query,
  }) {
    return _service.load(key: key, query: query);
  }

  Future<Map<String, dynamic>> submit({
    required String key,
    required Map<String, dynamic> body,
  }) {
    return _service.submit(key: key, body: body);
  }
}
