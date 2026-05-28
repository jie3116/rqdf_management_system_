import '../../../../core/network/api_client.dart';
import '../models/boarding_attendance_model.dart';
import '../models/boarding_dashboard_model.dart';
import '../models/boarding_savings_model.dart';

class BoardingDashboardService {
  BoardingDashboardService({required ApiClient apiClient})
      : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<BoardingDashboardModel> fetchDashboard() async {
    final data = await _apiClient.get('/boarding/dashboard');
    return BoardingDashboardModel.fromJson(data);
  }

  Future<BoardingAttendanceModel> fetchAttendance({
    int? dormitoryId,
    int? scheduleId,
    String? date,
  }) async {
    final query = <String>[];
    if (dormitoryId != null && dormitoryId > 0) {
      query.add('dormitory_id=$dormitoryId');
    }
    if (scheduleId != null && scheduleId > 0) {
      query.add('schedule_id=$scheduleId');
    }
    if (date != null && date.trim().isNotEmpty) {
      query.add('date=${Uri.encodeQueryComponent(date.trim())}');
    }
    final suffix = query.isEmpty ? '' : '?${query.join('&')}';
    final data = await _apiClient.get('/boarding/attendance$suffix');
    return BoardingAttendanceModel.fromJson(data);
  }

  Future<void> saveAttendance({
    required int dormitoryId,
    required int scheduleId,
    required String date,
    required List<BoardingAttendanceRecordInput> records,
  }) async {
    await _apiClient.post(
      '/boarding/attendance',
      body: <String, dynamic>{
        'dormitory_id': dormitoryId,
        'schedule_id': scheduleId,
        'date': date,
        'records': records.map((item) => item.toJson()).toList(),
      },
    );
  }

  Future<BoardingSavingsModel> fetchSavings() async {
    final data = await _apiClient.get('/boarding/savings');
    return BoardingSavingsModel.fromJson(data);
  }

  Future<void> setOfficerPin({
    String? oldPin,
    required String pin,
    required String pinConfirm,
  }) async {
    await _apiClient.post(
      '/boarding/savings/officer-pin',
      body: <String, dynamic>{
        'old_pin': oldPin ?? '',
        'pin': pin,
        'pin_confirm': pinConfirm,
      },
    );
  }

  Future<void> withdrawSavings({
    required int studentId,
    required int amount,
    required String studentPin,
    required String officerPin,
  }) async {
    await _apiClient.post(
      '/boarding/savings/withdraw',
      body: <String, dynamic>{
        'student_id': studentId,
        'amount': amount,
        'student_pin': studentPin,
        'officer_pin': officerPin,
      },
    );
  }
}
