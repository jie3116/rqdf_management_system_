import '../../../../core/utils/json_helper.dart';

class ChildModel {
  ChildModel({
    required this.id,
    required this.name,
    required this.className,
    this.avatarUrl,
  });

  final int id;
  final String name;
  final String className;
  final String? avatarUrl;

  factory ChildModel.fromJson(Map<String, dynamic> json) {
    return ChildModel(
      id: JsonHelper.asInt(json['id']),
      name: JsonHelper.asString(
        json['name'] ?? json['full_name'],
        fallback: '-',
      ),
      className: JsonHelper.asString(
        json['class_name'] ?? json['class'] ?? json['current_class_name'],
        fallback: '-',
      ),
      avatarUrl: JsonHelper.asString(json['avatar_url']).isEmpty
          ? null
          : JsonHelper.asString(json['avatar_url']),
    );
  }
}
