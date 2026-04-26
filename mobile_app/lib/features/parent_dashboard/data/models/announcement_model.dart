import '../../../../core/utils/json_helper.dart';

class AnnouncementModel {
  AnnouncementModel({
    required this.id,
    required this.title,
    required this.content,
    required this.authorLabel,
    required this.createdAt,
    required this.isUnread,
  });

  final int id;
  final String title;
  final String content;
  final String authorLabel;
  final String createdAt;
  final bool isUnread;

  factory AnnouncementModel.fromJson(Map<String, dynamic> json) {
    return AnnouncementModel(
      id: JsonHelper.asInt(json['id']),
      title: JsonHelper.asString(json['title'], fallback: '-'),
      content: JsonHelper.asString(json['content'], fallback: '-'),
      authorLabel: JsonHelper.asString(json['author_label'], fallback: 'Sistem'),
      createdAt: JsonHelper.asString(json['created_at'], fallback: '-'),
      isUnread: json['is_unread'] == true,
    );
  }
}
