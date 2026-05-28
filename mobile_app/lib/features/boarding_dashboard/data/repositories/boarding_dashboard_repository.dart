import '../models/boarding_attendance_model.dart';
import '../models/boarding_dashboard_model.dart';
import '../models/boarding_savings_model.dart';
import '../services/boarding_dashboard_service.dart';

class BoardingDashboardRepository {
  BoardingDashboardRepository(this._service);

  final BoardingDashboardService _service;

  Future<BoardingDashboardModel> getDashboard() {
    return _service.fetchDashboard();
  }

  Future<BoardingAttendanceModel> getAttendance({
    int? dormitoryId,
    int? scheduleId,
    String? date,
  }) {
    return _service.fetchAttendance(
      dormitoryId: dormitoryId,
      scheduleId: scheduleId,
      date: date,
    );
  }

  Future<void> saveAttendance({
    required int dormitoryId,
    required int scheduleId,
    required String date,
    required List<BoardingAttendanceRecordInput> records,
  }) {
    return _service.saveAttendance(
      dormitoryId: dormitoryId,
      scheduleId: scheduleId,
      date: date,
      records: records,
    );
  }

  Future<BoardingSavingsModel> getSavings() {
    return _service.fetchSavings();
  }

  Future<void> setOfficerPin({
    String? oldPin,
    required String pin,
    required String pinConfirm,
  }) {
    return _service.setOfficerPin(
      oldPin: oldPin,
      pin: pin,
      pinConfirm: pinConfirm,
    );
  }

  Future<void> withdrawSavings({
    required int studentId,
    required int amount,
    required String studentPin,
    required String officerPin,
  }) {
    return _service.withdrawSavings(
      studentId: studentId,
      amount: amount,
      studentPin: studentPin,
      officerPin: officerPin,
    );
  }
}
