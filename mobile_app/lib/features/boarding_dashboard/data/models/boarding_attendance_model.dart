import '../../../../core/utils/json_helper.dart';
import 'boarding_dashboard_model.dart';

class BoardingAttendanceModel {
  BoardingAttendanceModel({
    required this.date,
    required this.dayName,
    required this.selectedDormitoryId,
    required this.selectedScheduleId,
    required this.dormitories,
    required this.schedules,
    required this.students,
    required this.statusOptions,
  });

  final String date;
  final String dayName;
  final int selectedDormitoryId;
  final int selectedScheduleId;
  final List<BoardingDormitoryModel> dormitories;
  final List<BoardingScheduleModel> schedules;
  final List<BoardingStudentAttendanceModel> students;
  final List<BoardingStatusOption> statusOptions;

  factory BoardingAttendanceModel.fromJson(Map<String, dynamic> json) {
    return BoardingAttendanceModel(
      date: JsonHelper.asString(json['date']),
      dayName: JsonHelper.asString(json['day_name'], fallback: '-'),
      selectedDormitoryId: JsonHelper.asInt(json['selected_dormitory_id']),
      selectedScheduleId: JsonHelper.asInt(json['selected_schedule_id']),
      dormitories: JsonHelper.asList(json['dormitories'])
          .map(
              (item) => BoardingDormitoryModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
      schedules: JsonHelper.asList(json['schedules'])
          .map((item) => BoardingScheduleModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
      students: JsonHelper.asList(json['students'])
          .map((item) =>
              BoardingStudentAttendanceModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
      statusOptions: JsonHelper.asList(json['status_options'])
          .map((item) => BoardingStatusOption.fromJson(JsonHelper.asMap(item)))
          .toList(),
    );
  }
}

class BoardingStudentAttendanceModel {
  BoardingStudentAttendanceModel({
    required this.id,
    required this.nis,
    required this.name,
    required this.genderLabel,
    required this.status,
    required this.statusLabel,
    required this.notes,
  });

  final int id;
  final String nis;
  final String name;
  final String genderLabel;
  final String status;
  final String statusLabel;
  final String notes;

  factory BoardingStudentAttendanceModel.fromJson(Map<String, dynamic> json) {
    return BoardingStudentAttendanceModel(
      id: JsonHelper.asInt(json['id']),
      nis: JsonHelper.asString(json['nis'], fallback: '-'),
      name: JsonHelper.asString(json['name'], fallback: '-'),
      genderLabel: JsonHelper.asString(json['gender_label'], fallback: '-'),
      status: JsonHelper.asString(json['status']),
      statusLabel: JsonHelper.asString(json['status_label']),
      notes: JsonHelper.asString(json['notes']),
    );
  }
}

class BoardingStatusOption {
  BoardingStatusOption({required this.key, required this.label});

  final String key;
  final String label;

  factory BoardingStatusOption.fromJson(Map<String, dynamic> json) {
    return BoardingStatusOption(
      key: JsonHelper.asString(json['key']),
      label: JsonHelper.asString(json['label']),
    );
  }
}

class BoardingAttendanceRecordInput {
  BoardingAttendanceRecordInput({
    required this.studentId,
    required this.status,
    this.notes,
  });

  final int studentId;
  final String status;
  final String? notes;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'student_id': studentId,
      'status': status,
      'notes': notes ?? '',
    };
  }
}
