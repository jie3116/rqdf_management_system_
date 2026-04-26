import '../../../../core/utils/json_helper.dart';

class RecentActivityModel {
  RecentActivityModel({
    required this.type,
    required this.message,
    required this.createdAt,
  });

  final String type;
  final String message;
  final String createdAt;

  factory RecentActivityModel.fromJson(Map<String, dynamic> json) {
    return RecentActivityModel(
      type: JsonHelper.asString(json['type'], fallback: 'info'),
      message: JsonHelper.asString(json['message'], fallback: '-'),
      createdAt: JsonHelper.asString(json['created_at'], fallback: '-'),
    );
  }
}
