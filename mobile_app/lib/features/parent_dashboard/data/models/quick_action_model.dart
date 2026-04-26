import '../../../../core/utils/json_helper.dart';

class QuickActionModel {
  const QuickActionModel({
    required this.key,
    required this.label,
  });

  final String key;
  final String label;

  factory QuickActionModel.fromJson(Map<String, dynamic> json) {
    return QuickActionModel(
      key: JsonHelper.asString(json['key'], fallback: 'fitur'),
      label: JsonHelper.asString(json['label'], fallback: 'Fitur'),
    );
  }
}
