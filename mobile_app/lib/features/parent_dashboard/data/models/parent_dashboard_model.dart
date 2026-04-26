import '../../../../core/utils/json_helper.dart';
import 'announcement_model.dart';
import 'child_model.dart';
import 'dashboard_summary_model.dart';
import 'quick_action_model.dart';
import 'recent_activity_model.dart';

class ParentDashboardModel {
  ParentDashboardModel({
    required this.guardianName,
    required this.selectedChild,
    required this.summary,
    required this.children,
    required this.quickActions,
    required this.recentActivities,
    required this.announcements,
    required this.unreadAnnouncementsCount,
    required this.isMajlisParticipant,
  });

  final String guardianName;
  final ChildModel? selectedChild;
  final DashboardSummaryModel summary;
  final List<ChildModel> children;
  final List<QuickActionModel> quickActions;
  final List<RecentActivityModel> recentActivities;
  final List<AnnouncementModel> announcements;
  final int unreadAnnouncementsCount;
  final bool isMajlisParticipant;

  factory ParentDashboardModel.fromJson(Map<String, dynamic> json) {
    final children = JsonHelper.asList(json['children'])
        .map((item) => ChildModel.fromJson(JsonHelper.asMap(item)))
        .toList();
    final selectedChildMap = JsonHelper.asMap(json['selected_child']);
    final selectedChild =
        selectedChildMap.isEmpty ? null : ChildModel.fromJson(selectedChildMap);

    final quickActionsRaw = JsonHelper.asList(json['quick_actions']);
    final quickActions = quickActionsRaw
        .map((item) => QuickActionModel.fromJson(JsonHelper.asMap(item)))
        .toList();

    final activitiesRaw = JsonHelper.asList(json['recent_activities']);
    final activities = activitiesRaw
        .map((item) => RecentActivityModel.fromJson(JsonHelper.asMap(item)))
        .toList();
    final announcementsRaw = JsonHelper.asList(json['announcements']);
    final announcements = announcementsRaw
        .map((item) => AnnouncementModel.fromJson(JsonHelper.asMap(item)))
        .toList();

    return ParentDashboardModel(
      guardianName: JsonHelper.asString(json['guardian_name'], fallback: '-'),
      selectedChild:
          selectedChild ?? (children.isNotEmpty ? children.first : null),
      summary:
          DashboardSummaryModel.fromJson(JsonHelper.asMap(json['summary'])),
      children: children,
      quickActions:
          quickActions.isNotEmpty ? quickActions : _defaultQuickActions(),
      recentActivities: activities,
      announcements: announcements,
      unreadAnnouncementsCount: JsonHelper.asInt(
        json['unread_announcements_count'],
      ),
      isMajlisParticipant: json['is_majlis_participant'] == true,
    );
  }

  static List<QuickActionModel> _defaultQuickActions() {
    return const [
      QuickActionModel(key: 'pengumuman', label: 'Pengumuman'),
      QuickActionModel(key: 'keuangan', label: 'Keuangan'),
      QuickActionModel(key: 'tahfidz', label: 'Tahfidz'),
      QuickActionModel(key: 'jadwal', label: 'Jadwal'),
      QuickActionModel(key: 'nilai', label: 'Nilai'),
      QuickActionModel(key: 'absensi', label: 'Absensi'),
      QuickActionModel(key: 'perilaku', label: 'Perilaku'),
    ];
  }
}
