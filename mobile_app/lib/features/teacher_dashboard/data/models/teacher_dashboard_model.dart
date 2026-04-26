import '../../../../core/utils/json_helper.dart';
import '../../../parent_dashboard/data/models/announcement_model.dart';

class TeacherDashboardModel {
  TeacherDashboardModel({
    required this.profile,
    required this.summary,
    required this.announcements,
    required this.unreadAnnouncementsCount,
    required this.todayName,
    required this.todaySchedules,
    required this.teachingAssignments,
    required this.classOptions,
    required this.inputMenu,
    required this.recentTahfidz,
    required this.recentRecitation,
    required this.historyMenu,
    required this.homeroom,
  });

  final TeacherProfile profile;
  final TeacherSummary summary;
  final List<AnnouncementModel> announcements;
  final int unreadAnnouncementsCount;
  final String todayName;
  final List<TeacherScheduleItem> todaySchedules;
  final List<TeacherAssignment> teachingAssignments;
  final List<TeacherClassOption> classOptions;
  final List<TeacherMenuItem> inputMenu;
  final List<TeacherRecordItem> recentTahfidz;
  final List<TeacherRecordItem> recentRecitation;
  final List<TeacherMenuItem> historyMenu;
  final TeacherHomeroom homeroom;

  factory TeacherDashboardModel.fromJson(Map<String, dynamic> json) {
    return TeacherDashboardModel(
      profile: TeacherProfile.fromJson(JsonHelper.asMap(json['profile'])),
      summary: TeacherSummary.fromJson(JsonHelper.asMap(json['summary'])),
      announcements: JsonHelper.asList(json['announcements'])
          .map((item) => AnnouncementModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
      unreadAnnouncementsCount:
          JsonHelper.asInt(json['unread_announcements_count']),
      todayName: JsonHelper.asString(json['today_name'], fallback: '-'),
      todaySchedules: JsonHelper.asList(json['today_schedules'])
          .map((item) => TeacherScheduleItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
      teachingAssignments: JsonHelper.asList(json['teaching_assignments'])
          .map((item) => TeacherAssignment.fromJson(JsonHelper.asMap(item)))
          .toList(),
      classOptions: JsonHelper.asList(json['class_options'])
          .map((item) => TeacherClassOption.fromJson(JsonHelper.asMap(item)))
          .toList(),
      inputMenu: JsonHelper.asList(json['input_menu'])
          .map((item) => TeacherMenuItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
      recentTahfidz: JsonHelper.asList(json['recent_tahfidz'])
          .map((item) => TeacherRecordItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
      recentRecitation: JsonHelper.asList(json['recent_recitation'])
          .map((item) => TeacherRecordItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
      historyMenu: JsonHelper.asList(json['history_menu'])
          .map((item) => TeacherMenuItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
      homeroom: TeacherHomeroom.fromJson(JsonHelper.asMap(json['homeroom'])),
    );
  }
}

class TeacherProfile {
  TeacherProfile({
    required this.id,
    required this.fullName,
    required this.nip,
    required this.homeroomClassName,
    required this.totalClasses,
    required this.totalStudents,
  });

  final int id;
  final String fullName;
  final String nip;
  final String homeroomClassName;
  final int totalClasses;
  final int totalStudents;

  factory TeacherProfile.fromJson(Map<String, dynamic> json) {
    return TeacherProfile(
      id: JsonHelper.asInt(json['id']),
      fullName: JsonHelper.asString(json['full_name'], fallback: '-'),
      nip: JsonHelper.asString(json['nip'], fallback: '-'),
      homeroomClassName: JsonHelper.asString(
        json['homeroom_class_name'],
        fallback: 'Tidak Menjabat',
      ),
      totalClasses: JsonHelper.asInt(json['total_classes']),
      totalStudents: JsonHelper.asInt(json['total_students']),
    );
  }
}

class TeacherSummary {
  TeacherSummary({
    required this.todayScheduleCount,
    required this.homeroomLabel,
    required this.todayTahfidzCount,
    required this.todayRecitationCount,
    required this.todayEvaluationCount,
    required this.boarding,
  });

  final int todayScheduleCount;
  final String homeroomLabel;
  final int todayTahfidzCount;
  final int todayRecitationCount;
  final int todayEvaluationCount;
  final TeacherBoardingSummary boarding;

  factory TeacherSummary.fromJson(Map<String, dynamic> json) {
    return TeacherSummary(
      todayScheduleCount: JsonHelper.asInt(json['today_schedule_count']),
      homeroomLabel: JsonHelper.asString(
        json['homeroom_label'],
        fallback: 'Tidak Menjabat',
      ),
      todayTahfidzCount: JsonHelper.asInt(json['today_tahfidz_count']),
      todayRecitationCount: JsonHelper.asInt(json['today_recitation_count']),
      todayEvaluationCount: JsonHelper.asInt(json['today_evaluation_count']),
      boarding:
          TeacherBoardingSummary.fromJson(JsonHelper.asMap(json['boarding'])),
    );
  }
}

class TeacherBoardingSummary {
  TeacherBoardingSummary({
    required this.hadir,
    required this.sakit,
    required this.izin,
    required this.alpa,
    required this.belumInput,
  });

  final int hadir;
  final int sakit;
  final int izin;
  final int alpa;
  final int belumInput;

  factory TeacherBoardingSummary.fromJson(Map<String, dynamic> json) {
    return TeacherBoardingSummary(
      hadir: JsonHelper.asInt(json['hadir']),
      sakit: JsonHelper.asInt(json['sakit']),
      izin: JsonHelper.asInt(json['izin']),
      alpa: JsonHelper.asInt(json['alpa']),
      belumInput: JsonHelper.asInt(json['belum_input']),
    );
  }
}

class TeacherScheduleItem {
  TeacherScheduleItem({
    required this.id,
    required this.classId,
    required this.className,
    required this.subjectId,
    required this.majlisSubjectId,
    required this.subjectName,
    required this.startTime,
    required this.endTime,
  });

  final int id;
  final int classId;
  final int subjectId;
  final int majlisSubjectId;
  final String className;
  final String subjectName;
  final String startTime;
  final String endTime;

  String get timeRange {
    if (startTime == '-' && endTime == '-') return '-';
    return '$startTime - $endTime';
  }

  factory TeacherScheduleItem.fromJson(Map<String, dynamic> json) {
    return TeacherScheduleItem(
      id: JsonHelper.asInt(json['id']),
      classId: JsonHelper.asInt(json['class_id']),
      className: JsonHelper.asString(json['class_name'], fallback: '-'),
      subjectId: JsonHelper.asInt(json['subject_id']),
      majlisSubjectId: JsonHelper.asInt(json['majlis_subject_id']),
      subjectName: JsonHelper.asString(json['subject_name'], fallback: '-'),
      startTime: JsonHelper.asString(json['start_time'], fallback: '-'),
      endTime: JsonHelper.asString(json['end_time'], fallback: '-'),
    );
  }
}

class TeacherAssignment {
  TeacherAssignment({
    required this.classId,
    required this.className,
    required this.subjectId,
    required this.majlisSubjectId,
    required this.subjectName,
  });

  final int classId;
  final String className;
  final int subjectId;
  final int majlisSubjectId;
  final String subjectName;

  factory TeacherAssignment.fromJson(Map<String, dynamic> json) {
    return TeacherAssignment(
      classId: JsonHelper.asInt(json['class_id']),
      className: JsonHelper.asString(json['class_name'], fallback: '-'),
      subjectId: JsonHelper.asInt(json['subject_id']),
      majlisSubjectId: JsonHelper.asInt(json['majlis_subject_id']),
      subjectName: JsonHelper.asString(json['subject_name'], fallback: '-'),
    );
  }
}

class TeacherClassOption {
  TeacherClassOption({
    required this.id,
    required this.name,
  });

  final int id;
  final String name;

  factory TeacherClassOption.fromJson(Map<String, dynamic> json) {
    return TeacherClassOption(
      id: JsonHelper.asInt(json['id']),
      name: JsonHelper.asString(json['name'], fallback: '-'),
    );
  }
}

class TeacherMenuItem {
  TeacherMenuItem({
    required this.key,
    required this.label,
    required this.description,
  });

  final String key;
  final String label;
  final String description;

  factory TeacherMenuItem.fromJson(Map<String, dynamic> json) {
    return TeacherMenuItem(
      key: JsonHelper.asString(json['key'], fallback: '-'),
      label: JsonHelper.asString(json['label'], fallback: '-'),
      description: JsonHelper.asString(json['description'], fallback: '-'),
    );
  }
}

class TeacherRecordItem {
  TeacherRecordItem({
    required this.id,
    required this.participantName,
    required this.date,
    required this.detail,
    required this.score,
  });

  final int id;
  final String participantName;
  final String date;
  final String detail;
  final num score;

  factory TeacherRecordItem.fromJson(Map<String, dynamic> json) {
    return TeacherRecordItem(
      id: JsonHelper.asInt(json['id']),
      participantName: JsonHelper.asString(
        json['participant_name'],
        fallback: '-',
      ),
      date: JsonHelper.asString(json['date'], fallback: '-'),
      detail: JsonHelper.asString(json['detail'], fallback: '-'),
      score: JsonHelper.asDouble(json['score']),
    );
  }
}

class TeacherHomeroom {
  TeacherHomeroom({
    required this.available,
    required this.classId,
    required this.className,
    required this.studentCount,
    required this.majlisCount,
    required this.menu,
  });

  final bool available;
  final int classId;
  final String className;
  final int studentCount;
  final int majlisCount;
  final List<TeacherMenuItem> menu;

  factory TeacherHomeroom.fromJson(Map<String, dynamic> json) {
    return TeacherHomeroom(
      available: json['available'] == true,
      classId: JsonHelper.asInt(json['class_id']),
      className: JsonHelper.asString(json['class_name'], fallback: '-'),
      studentCount: JsonHelper.asInt(json['student_count']),
      majlisCount: JsonHelper.asInt(json['majlis_count']),
      menu: JsonHelper.asList(json['menu'])
          .map((item) => TeacherMenuItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
    );
  }
}
