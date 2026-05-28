import 'package:flutter/foundation.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../shared/models/view_state.dart';
import '../../data/models/boarding_attendance_model.dart';
import '../../data/models/boarding_dashboard_model.dart';
import '../../data/models/boarding_savings_model.dart';
import '../../data/repositories/boarding_dashboard_repository.dart';

class BoardingDashboardProvider extends ChangeNotifier {
  BoardingDashboardProvider({required BoardingDashboardRepository repository})
      : _repository = repository;

  final BoardingDashboardRepository _repository;

  ViewState dashboardState = ViewState.initial;
  ViewState attendanceState = ViewState.initial;
  ViewState savingsState = ViewState.initial;
  BoardingDashboardModel? dashboard;
  BoardingAttendanceModel? attendance;
  BoardingSavingsModel? savings;
  String? dashboardError;
  String? attendanceError;
  String? savingsError;
  bool isSavingAttendance = false;
  bool isSavingOfficerPin = false;
  bool isWithdrawingSavings = false;
  bool _isAuthenticated = false;

  void setSession({required bool isAuthenticated}) {
    _isAuthenticated = isAuthenticated;
    if (!isAuthenticated) {
      dashboardState = ViewState.initial;
      attendanceState = ViewState.initial;
      savingsState = ViewState.initial;
      dashboard = null;
      attendance = null;
      savings = null;
      dashboardError = null;
      attendanceError = null;
      savingsError = null;
      isSavingAttendance = false;
      isSavingOfficerPin = false;
      isWithdrawingSavings = false;
      notifyListeners();
    }
  }

  Future<void> fetchDashboard({bool forceRefresh = false}) async {
    if (!_isAuthenticated) return;
    if (!forceRefresh &&
        dashboardState == ViewState.success &&
        dashboard != null) {
      return;
    }

    dashboardState = ViewState.loading;
    dashboardError = null;
    notifyListeners();
    try {
      dashboard = await _repository.getDashboard();
      dashboardState = ViewState.success;
    } on ApiException catch (error) {
      dashboardState = ViewState.error;
      dashboardError = error.message;
    } catch (_) {
      dashboardState = ViewState.error;
      dashboardError = 'Data asrama gagal dimuat.';
    }
    notifyListeners();
  }

  Future<void> fetchAttendance({
    int? dormitoryId,
    int? scheduleId,
    String? date,
  }) async {
    if (!_isAuthenticated) return;
    attendanceState = ViewState.loading;
    attendanceError = null;
    notifyListeners();
    try {
      attendance = await _repository.getAttendance(
        dormitoryId: dormitoryId,
        scheduleId: scheduleId,
        date: date,
      );
      attendanceState = ViewState.success;
    } on ApiException catch (error) {
      attendanceState = ViewState.error;
      attendanceError = error.message;
    } catch (_) {
      attendanceState = ViewState.error;
      attendanceError = 'Form absensi asrama gagal dimuat.';
    }
    notifyListeners();
  }

  Future<String?> saveAttendance({
    required int dormitoryId,
    required int scheduleId,
    required String date,
    required List<BoardingAttendanceRecordInput> records,
  }) async {
    isSavingAttendance = true;
    notifyListeners();
    try {
      await _repository.saveAttendance(
        dormitoryId: dormitoryId,
        scheduleId: scheduleId,
        date: date,
        records: records,
      );
      return null;
    } on ApiException catch (error) {
      return error.message;
    } catch (_) {
      return 'Absensi asrama gagal disimpan.';
    } finally {
      isSavingAttendance = false;
      notifyListeners();
    }
  }

  Future<void> fetchSavings({bool forceRefresh = false}) async {
    if (!_isAuthenticated) return;
    if (!forceRefresh && savingsState == ViewState.success && savings != null) {
      return;
    }

    savingsState = ViewState.loading;
    savingsError = null;
    notifyListeners();
    try {
      savings = await _repository.getSavings();
      savingsState = ViewState.success;
    } on ApiException catch (error) {
      savingsState = ViewState.error;
      savingsError = error.message;
    } catch (_) {
      savingsState = ViewState.error;
      savingsError = 'Data tabungan santri gagal dimuat.';
    }
    notifyListeners();
  }

  Future<String?> setOfficerPin({
    String? oldPin,
    required String pin,
    required String pinConfirm,
  }) async {
    isSavingOfficerPin = true;
    notifyListeners();
    try {
      await _repository.setOfficerPin(
        oldPin: oldPin,
        pin: pin,
        pinConfirm: pinConfirm,
      );
      return null;
    } on ApiException catch (error) {
      return error.message;
    } catch (_) {
      return 'PIN petugas gagal disimpan.';
    } finally {
      isSavingOfficerPin = false;
      notifyListeners();
    }
  }

  Future<String?> withdrawSavings({
    required int studentId,
    required int amount,
    required String studentPin,
    required String officerPin,
  }) async {
    isWithdrawingSavings = true;
    notifyListeners();
    try {
      await _repository.withdrawSavings(
        studentId: studentId,
        amount: amount,
        studentPin: studentPin,
        officerPin: officerPin,
      );
      return null;
    } on ApiException catch (error) {
      return error.message;
    } catch (_) {
      return 'Penarikan tabungan gagal diproses.';
    } finally {
      isWithdrawingSavings = false;
      notifyListeners();
    }
  }
}
