import '../../../../core/utils/json_helper.dart';
import '../../../../core/constants/quran_options.dart';

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
    final rawMemorizationProgress = JsonHelper.asString(
      json['memorization_progress'] ?? json['tahfidz_progress'],
      fallback: '-',
    );

    return DashboardSummaryModel(
      billingTotal: JsonHelper.asDouble(
        json['billing_total'] ?? json['bill_total'] ?? json['total_billing'],
      ),
      violationPoints: JsonHelper.asInt(
        json['violation_points'] ?? json['points'] ?? json['poin_pelanggaran'],
      ),
      memorizationProgress:
          _compactMemorizationProgress(rawMemorizationProgress),
      attendanceStatus: JsonHelper.asString(
        json['attendance_status'] ?? json['attendance_note'],
        fallback: '-',
      ),
    );
  }

  static String _compactMemorizationProgress(String value) {
    final raw = value.trim();
    if (raw.isEmpty || raw == '-') return '-';

    final parts = raw.split('|');
    final prefix = parts.first.trim();
    final target = parts.length > 1 ? parts.sublist(1).join('|').trim() : raw;

    final match = RegExp(r'^(.+?)(?:\s*[:/]\s*|\s+)(\d+)$').firstMatch(target);
    if (match == null) return raw;

    final surahName = (match.group(1) ?? '').trim();
    final ayat = (match.group(2) ?? '').trim();
    if (surahName.isEmpty || ayat.isEmpty) return raw;

    final surahNumber = _surahNumberFromName(surahName);
    if (surahNumber == null) return raw;

    final quranText = 'QS $surahNumber/$ayat';
    if (parts.length > 1 && prefix.isNotEmpty) {
      return '$prefix | $quranText';
    }
    return quranText;
  }

  static int? _surahNumberFromName(String surahName) {
    final normalizedTarget = _normalizeSurahName(surahName);
    for (final option in kQuranSurahOptions) {
      if (_normalizeSurahName(option.name) == normalizedTarget) {
        return option.number;
      }
    }
    return null;
  }

  static String _normalizeSurahName(String value) {
    return value.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
  }
}
