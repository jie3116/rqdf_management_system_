import '../../../../core/utils/json_helper.dart';

class BoardingDashboardModel {
  BoardingDashboardModel({
    required this.profile,
    required this.today,
    required this.todayName,
    required this.summary,
    required this.dormitories,
    required this.todaySchedules,
  });

  final BoardingGuardianProfile profile;
  final String today;
  final String todayName;
  final BoardingSummary summary;
  final List<BoardingDormitoryModel> dormitories;
  final List<BoardingScheduleModel> todaySchedules;

  factory BoardingDashboardModel.fromJson(Map<String, dynamic> json) {
    return BoardingDashboardModel(
      profile:
          BoardingGuardianProfile.fromJson(JsonHelper.asMap(json['profile'])),
      today: JsonHelper.asString(json['today']),
      todayName: JsonHelper.asString(json['today_name'], fallback: 'Hari ini'),
      summary: BoardingSummary.fromJson(JsonHelper.asMap(json['summary'])),
      dormitories: JsonHelper.asList(json['dormitories'])
          .map(
              (item) => BoardingDormitoryModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
      todaySchedules: JsonHelper.asList(json['today_schedules'])
          .map((item) => BoardingScheduleModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
    );
  }
}

class BoardingGuardianProfile {
  BoardingGuardianProfile({required this.name, required this.phone});

  final String name;
  final String phone;

  factory BoardingGuardianProfile.fromJson(Map<String, dynamic> json) {
    return BoardingGuardianProfile(
      name: JsonHelper.asString(json['name'], fallback: '-'),
      phone: JsonHelper.asString(json['phone'], fallback: '-'),
    );
  }
}

class BoardingSummary {
  BoardingSummary({
    required this.dormitoryCount,
    required this.studentCount,
    required this.attendanceToday,
    required this.scheduleToday,
  });

  final int dormitoryCount;
  final int studentCount;
  final int attendanceToday;
  final int scheduleToday;

  factory BoardingSummary.fromJson(Map<String, dynamic> json) {
    return BoardingSummary(
      dormitoryCount: JsonHelper.asInt(json['dormitory_count']),
      studentCount: JsonHelper.asInt(json['student_count']),
      attendanceToday: JsonHelper.asInt(json['attendance_today']),
      scheduleToday: JsonHelper.asInt(json['schedule_today']),
    );
  }
}

class BoardingDormitoryModel {
  BoardingDormitoryModel({
    required this.id,
    required this.name,
    required this.genderLabel,
    required this.capacity,
    required this.studentCount,
  });

  final int id;
  final String name;
  final String genderLabel;
  final int capacity;
  final int studentCount;

  factory BoardingDormitoryModel.fromJson(Map<String, dynamic> json) {
    return BoardingDormitoryModel(
      id: JsonHelper.asInt(json['id']),
      name: JsonHelper.asString(json['name'], fallback: '-'),
      genderLabel: JsonHelper.asString(json['gender_label'], fallback: '-'),
      capacity: JsonHelper.asInt(json['capacity']),
      studentCount: JsonHelper.asInt(json['student_count']),
    );
  }
}

class BoardingScheduleModel {
  BoardingScheduleModel({
    required this.id,
    required this.activityName,
    required this.startTime,
    required this.endTime,
    required this.dormitoryId,
    required this.dormitoryName,
  });

  final int id;
  final String activityName;
  final String startTime;
  final String endTime;
  final int dormitoryId;
  final String dormitoryName;

  factory BoardingScheduleModel.fromJson(Map<String, dynamic> json) {
    return BoardingScheduleModel(
      id: JsonHelper.asInt(json['id']),
      activityName: JsonHelper.asString(json['activity_name'], fallback: '-'),
      startTime: JsonHelper.asString(json['start_time'], fallback: '-'),
      endTime: JsonHelper.asString(json['end_time'], fallback: '-'),
      dormitoryId: JsonHelper.asInt(json['dormitory_id']),
      dormitoryName: JsonHelper.asString(json['dormitory_name'], fallback: '-'),
    );
  }
}
