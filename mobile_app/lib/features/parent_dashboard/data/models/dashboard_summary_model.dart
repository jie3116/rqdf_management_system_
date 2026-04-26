import '../../../../core/utils/json_helper.dart';

class DashboardSummaryModel {
  DashboardSummaryModel({
    required this.billingTotal,
    required this.violationPoints,
    required this.memorizationProgress,
    required this.attendanceStatus,
  });

  final double billingTotal;
  final int violationPoints;
  final String memorizationProgress;
  final String attendanceStatus;

  factory DashboardSummaryModel.fromJson(Map<String, dynamic> json) {
    return DashboardSummaryModel(
      billingTotal: JsonHelper.asDouble(
        json['billing_total'] ?? json['bill_total'] ?? json['total_billing'],
      ),
      violationPoints: JsonHelper.asInt(
        json['violation_points'] ?? json['points'] ?? json['poin_pelanggaran'],
      ),
      memorizationProgress: JsonHelper.asString(
        json['memorization_progress'] ?? json['tahfidz_progress'],
        fallback: '-',
      ),
      attendanceStatus: JsonHelper.asString(
        json['attendance_status'] ?? json['attendance_note'],
        fallback: '-',
      ),
    );
  }
}
