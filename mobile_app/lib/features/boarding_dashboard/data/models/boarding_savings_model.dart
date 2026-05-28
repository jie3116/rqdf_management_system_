import '../../../../core/utils/json_helper.dart';

class BoardingSavingsModel {
  BoardingSavingsModel({
    required this.officerPinExists,
    required this.officerPinLockedMinutes,
    required this.summary,
    required this.students,
  });

  final bool officerPinExists;
  final int officerPinLockedMinutes;
  final BoardingSavingsSummary summary;
  final List<BoardingSavingsStudentModel> students;

  factory BoardingSavingsModel.fromJson(Map<String, dynamic> json) {
    return BoardingSavingsModel(
      officerPinExists: json['officer_pin_exists'] == true,
      officerPinLockedMinutes:
          JsonHelper.asInt(json['officer_pin_locked_minutes']),
      summary:
          BoardingSavingsSummary.fromJson(JsonHelper.asMap(json['summary'])),
      students: JsonHelper.asList(json['students'])
          .map((item) =>
              BoardingSavingsStudentModel.fromJson(JsonHelper.asMap(item)))
          .toList(),
    );
  }
}

class BoardingSavingsSummary {
  BoardingSavingsSummary({
    required this.studentCount,
    required this.accountCount,
    required this.totalBalance,
  });

  final int studentCount;
  final int accountCount;
  final int totalBalance;

  factory BoardingSavingsSummary.fromJson(Map<String, dynamic> json) {
    return BoardingSavingsSummary(
      studentCount: JsonHelper.asInt(json['student_count']),
      accountCount: JsonHelper.asInt(json['account_count']),
      totalBalance: JsonHelper.asInt(json['total_balance']),
    );
  }
}

class BoardingSavingsStudentModel {
  BoardingSavingsStudentModel({
    required this.id,
    required this.nis,
    required this.name,
    required this.dormitoryName,
    required this.balance,
    required this.hasPin,
    required this.pinLocked,
  });

  final int id;
  final String nis;
  final String name;
  final String dormitoryName;
  final int balance;
  final bool hasPin;
  final bool pinLocked;

  factory BoardingSavingsStudentModel.fromJson(Map<String, dynamic> json) {
    return BoardingSavingsStudentModel(
      id: JsonHelper.asInt(json['id']),
      nis: JsonHelper.asString(json['nis'], fallback: '-'),
      name: JsonHelper.asString(json['name'], fallback: '-'),
      dormitoryName: JsonHelper.asString(json['dormitory_name'], fallback: '-'),
      balance: JsonHelper.asInt(json['balance']),
      hasPin: json['has_pin'] == true,
      pinLocked: json['pin_locked'] == true,
    );
  }
}
