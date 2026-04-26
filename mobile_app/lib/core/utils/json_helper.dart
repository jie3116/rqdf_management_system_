class JsonHelper {
  const JsonHelper._();

  static String asString(dynamic value, {String fallback = ''}) {
    if (value == null) return fallback;
    final text = value.toString().trim();
    return text.isEmpty ? fallback : text;
  }

  static int asInt(dynamic value, {int fallback = 0}) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '') ?? fallback;
  }

  static double asDouble(dynamic value, {double fallback = 0}) {
    if (value is double) return value;
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? fallback;
  }

  static List<dynamic> asList(dynamic value) {
    return value is List<dynamic> ? value : <dynamic>[];
  }

  static Map<String, dynamic> asMap(dynamic value) {
    return value is Map<String, dynamic> ? value : <String, dynamic>{};
  }
}
