class QuickActionResultModel {
  QuickActionResultModel({
    required this.key,
    required this.label,
    required this.payload,
  });

  final String key;
  final String label;
  final Map<String, dynamic> payload;
}
