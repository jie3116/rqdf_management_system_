class AppDateFormatter {
  static const List<String> _monthNames = <String>[
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'Mei',
    'Jun',
    'Jul',
    'Agu',
    'Sep',
    'Okt',
    'Nov',
    'Des',
  ];

  static String shortDate(String? raw, {String fallback = '-'}) {
    final parsed = _tryParse(raw);
    if (parsed == null) {
      return fallback;
    }
    final monthName = _monthNames[parsed.month - 1];
    return '${parsed.day} $monthName ${parsed.year}';
  }

  static String dateLabel(
    String? raw, {
    String prefix = 'Dibuat',
    String fallback = '-',
  }) {
    final value = shortDate(raw, fallback: fallback);
    if (value == fallback) {
      return fallback;
    }
    return '$prefix $value';
  }

  static DateTime? _tryParse(String? raw) {
    if (raw == null || raw.trim().isEmpty || raw.trim() == '-') {
      return null;
    }
    return DateTime.tryParse(raw.trim());
  }
}
