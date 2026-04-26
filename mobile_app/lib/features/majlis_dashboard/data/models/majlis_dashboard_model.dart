import '../../../../core/utils/json_helper.dart';

class MajlisDashboardModel {
  MajlisDashboardModel({
    required this.profile,
    required this.summary,
    required this.announcements,
    required this.unreadAnnouncementsCount,
    required this.tahfidzRecords,
    required this.recitationRecords,
    required this.evaluationRecords,
    required this.attendance,
    required this.scheduleDays,
    required this.finance,
  });

  final MajlisProfile profile;
  final MajlisSummary summary;
  final List<MajlisAnnouncement> announcements;
  final int unreadAnnouncementsCount;
  final List<MajlisTahfidzRecord> tahfidzRecords;
  final List<MajlisRecitationRecord> recitationRecords;
  final List<MajlisEvaluationRecord> evaluationRecords;
  final MajlisAttendance attendance;
  final List<MajlisScheduleDay> scheduleDays;
  final MajlisFinance finance;

  factory MajlisDashboardModel.fromJson(Map<String, dynamic> json) {
    return MajlisDashboardModel(
      profile: MajlisProfile.fromJson(JsonHelper.asMap(json['profile'])),
      summary: MajlisSummary.fromJson(JsonHelper.asMap(json['summary'])),
      announcements: JsonHelper.asList(json['announcements'])
          .map((item) => MajlisAnnouncement.fromJson(JsonHelper.asMap(item)))
          .toList(),
      unreadAnnouncementsCount:
          JsonHelper.asInt(json['unread_announcements_count']),
      tahfidzRecords: JsonHelper.asList(json['tahfidz_records'])
          .map((item) => MajlisTahfidzRecord.fromJson(JsonHelper.asMap(item)))
          .toList(),
      recitationRecords: JsonHelper.asList(json['recitation_records'])
          .map(
            (item) => MajlisRecitationRecord.fromJson(JsonHelper.asMap(item)),
          )
          .toList(),
      evaluationRecords: JsonHelper.asList(json['evaluation_records'])
          .map(
            (item) => MajlisEvaluationRecord.fromJson(JsonHelper.asMap(item)),
          )
          .toList(),
      attendance: MajlisAttendance.fromJson(JsonHelper.asMap(json['attendance'])),
      scheduleDays: JsonHelper.asList(json['schedule_days'])
          .map((item) => MajlisScheduleDay.fromJson(JsonHelper.asMap(item)))
          .toList(),
      finance: MajlisFinance.fromJson(JsonHelper.asMap(json['finance'])),
    );
  }
}

class MajlisProfile {
  MajlisProfile({
    required this.id,
    required this.fullName,
    required this.phone,
    required this.address,
    required this.job,
    required this.majlisClassId,
    required this.majlisClassName,
    required this.joinDate,
    required this.hasExternalProfile,
    required this.hasParentProfile,
  });

  final int id;
  final String fullName;
  final String phone;
  final String address;
  final String job;
  final int majlisClassId;
  final String majlisClassName;
  final String joinDate;
  final bool hasExternalProfile;
  final bool hasParentProfile;

  factory MajlisProfile.fromJson(Map<String, dynamic> json) {
    return MajlisProfile(
      id: JsonHelper.asInt(json['id']),
      fullName: JsonHelper.asString(json['full_name'], fallback: '-'),
      phone: JsonHelper.asString(json['phone'], fallback: '-'),
      address: JsonHelper.asString(json['address'], fallback: '-'),
      job: JsonHelper.asString(json['job'], fallback: '-'),
      majlisClassId: JsonHelper.asInt(json['majlis_class_id']),
      majlisClassName: JsonHelper.asString(
        json['majlis_class_name'],
        fallback: '-',
      ),
      joinDate: JsonHelper.asString(json['join_date'], fallback: '-'),
      hasExternalProfile: json['has_external_profile'] == true,
      hasParentProfile: json['has_parent_profile'] == true,
    );
  }
}

class MajlisSummary {
  MajlisSummary({
    required this.totalJuz,
    required this.lastTargetText,
    required this.updatedAt,
  });

  final num totalJuz;
  final String lastTargetText;
  final String updatedAt;

  factory MajlisSummary.fromJson(Map<String, dynamic> json) {
    return MajlisSummary(
      totalJuz: JsonHelper.asDouble(json['total_juz']),
      lastTargetText: JsonHelper.asString(
        json['last_target_text'],
        fallback: '-',
      ),
      updatedAt: JsonHelper.asString(json['updated_at'], fallback: '-'),
    );
  }
}

class MajlisAnnouncement {
  MajlisAnnouncement({
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

  factory MajlisAnnouncement.fromJson(Map<String, dynamic> json) {
    return MajlisAnnouncement(
      id: JsonHelper.asInt(json['id']),
      title: JsonHelper.asString(json['title'], fallback: '-'),
      content: JsonHelper.asString(json['content'], fallback: '-'),
      authorLabel: JsonHelper.asString(json['author_label'], fallback: 'Sistem'),
      createdAt: JsonHelper.asString(json['created_at'], fallback: '-'),
      isUnread: json['is_unread'] == true,
    );
  }
}

class MajlisTahfidzRecord {
  MajlisTahfidzRecord({
    required this.id,
    required this.date,
    required this.typeLabel,
    required this.surah,
    required this.ayatStart,
    required this.ayatEnd,
    required this.quality,
    required this.score,
  });

  final int id;
  final String date;
  final String typeLabel;
  final String surah;
  final int ayatStart;
  final int ayatEnd;
  final String quality;
  final num score;

  String get ayatRange {
    if (ayatStart <= 0 && ayatEnd <= 0) return '-';
    if (ayatEnd <= 0 || ayatStart == ayatEnd) return '$ayatStart';
    return '$ayatStart-$ayatEnd';
  }

  factory MajlisTahfidzRecord.fromJson(Map<String, dynamic> json) {
    return MajlisTahfidzRecord(
      id: JsonHelper.asInt(json['id']),
      date: JsonHelper.asString(json['date'], fallback: '-'),
      typeLabel: JsonHelper.asString(json['type_label'], fallback: '-'),
      surah: JsonHelper.asString(json['surah'], fallback: '-'),
      ayatStart: JsonHelper.asInt(json['ayat_start']),
      ayatEnd: JsonHelper.asInt(json['ayat_end']),
      quality: JsonHelper.asString(json['quality'], fallback: '-'),
      score: JsonHelper.asDouble(json['score']),
    );
  }
}

class MajlisRecitationRecord {
  MajlisRecitationRecord({
    required this.id,
    required this.date,
    required this.sourceLabel,
    required this.surah,
    required this.ayatStart,
    required this.ayatEnd,
    required this.bookName,
    required this.pageStart,
    required this.pageEnd,
    required this.score,
  });

  final int id;
  final String date;
  final String sourceLabel;
  final String surah;
  final int ayatStart;
  final int ayatEnd;
  final String bookName;
  final int pageStart;
  final int pageEnd;
  final num score;

  String get materialText {
    if (bookName != '-') {
      if (pageStart > 0 && pageEnd > 0) {
        return '$bookName (Hal. $pageStart-$pageEnd)';
      }
      return bookName;
    }
    if (ayatStart > 0 && ayatEnd > 0) {
      return '$surah ($ayatStart-$ayatEnd)';
    }
    return surah;
  }

  factory MajlisRecitationRecord.fromJson(Map<String, dynamic> json) {
    return MajlisRecitationRecord(
      id: JsonHelper.asInt(json['id']),
      date: JsonHelper.asString(json['date'], fallback: '-'),
      sourceLabel: JsonHelper.asString(
        json['recitation_source_label'],
        fallback: '-',
      ),
      surah: JsonHelper.asString(json['surah'], fallback: '-'),
      ayatStart: JsonHelper.asInt(json['ayat_start']),
      ayatEnd: JsonHelper.asInt(json['ayat_end']),
      bookName: JsonHelper.asString(json['book_name'], fallback: '-'),
      pageStart: JsonHelper.asInt(json['page_start']),
      pageEnd: JsonHelper.asInt(json['page_end']),
      score: JsonHelper.asDouble(json['score']),
    );
  }
}

class MajlisEvaluationRecord {
  MajlisEvaluationRecord({
    required this.id,
    required this.date,
    required this.periodTypeLabel,
    required this.periodLabel,
    required this.score,
    required this.makhrajErrors,
    required this.tajwidErrors,
    required this.harakatErrors,
  });

  final int id;
  final String date;
  final String periodTypeLabel;
  final String periodLabel;
  final num score;
  final int makhrajErrors;
  final int tajwidErrors;
  final int harakatErrors;

  String get periodText {
    if (periodLabel == '-' || periodLabel.isEmpty) return periodTypeLabel;
    return '$periodTypeLabel - $periodLabel';
  }

  factory MajlisEvaluationRecord.fromJson(Map<String, dynamic> json) {
    return MajlisEvaluationRecord(
      id: JsonHelper.asInt(json['id']),
      date: JsonHelper.asString(json['date'], fallback: '-'),
      periodTypeLabel: JsonHelper.asString(
        json['period_type_label'],
        fallback: '-',
      ),
      periodLabel: JsonHelper.asString(json['period_label'], fallback: '-'),
      score: JsonHelper.asDouble(json['score']),
      makhrajErrors: JsonHelper.asInt(json['makhraj_errors']),
      tajwidErrors: JsonHelper.asInt(json['tajwid_errors']),
      harakatErrors: JsonHelper.asInt(json['harakat_errors']),
    );
  }
}

class MajlisAttendance {
  MajlisAttendance({
    required this.records,
    required this.recap,
  });

  final List<MajlisAttendanceRecord> records;
  final MajlisAttendanceRecap recap;

  factory MajlisAttendance.fromJson(Map<String, dynamic> json) {
    return MajlisAttendance(
      records: JsonHelper.asList(json['records'])
          .map((item) => MajlisAttendanceRecord.fromJson(JsonHelper.asMap(item)))
          .toList(),
      recap: MajlisAttendanceRecap.fromJson(JsonHelper.asMap(json['recap'])),
    );
  }
}

class MajlisAttendanceRecord {
  MajlisAttendanceRecord({
    required this.id,
    required this.date,
    required this.status,
    required this.statusLabel,
    required this.className,
    required this.teacherName,
  });

  final int id;
  final String date;
  final String status;
  final String statusLabel;
  final String className;
  final String teacherName;

  factory MajlisAttendanceRecord.fromJson(Map<String, dynamic> json) {
    return MajlisAttendanceRecord(
      id: JsonHelper.asInt(json['id']),
      date: JsonHelper.asString(json['date'], fallback: '-'),
      status: JsonHelper.asString(json['status'], fallback: '-'),
      statusLabel: JsonHelper.asString(json['status_label'], fallback: '-'),
      className: JsonHelper.asString(json['class_name'], fallback: '-'),
      teacherName: JsonHelper.asString(json['teacher_name'], fallback: '-'),
    );
  }
}

class MajlisAttendanceRecap {
  MajlisAttendanceRecap({
    required this.hadir,
    required this.sakit,
    required this.izin,
    required this.alpa,
  });

  final int hadir;
  final int sakit;
  final int izin;
  final int alpa;

  factory MajlisAttendanceRecap.fromJson(Map<String, dynamic> json) {
    return MajlisAttendanceRecap(
      hadir: JsonHelper.asInt(json['hadir']),
      sakit: JsonHelper.asInt(json['sakit']),
      izin: JsonHelper.asInt(json['izin']),
      alpa: JsonHelper.asInt(json['alpa']),
    );
  }
}

class MajlisScheduleDay {
  MajlisScheduleDay({
    required this.day,
    required this.items,
  });

  final String day;
  final List<MajlisScheduleItem> items;

  factory MajlisScheduleDay.fromJson(Map<String, dynamic> json) {
    return MajlisScheduleDay(
      day: JsonHelper.asString(json['day'], fallback: '-'),
      items: JsonHelper.asList(json['items'])
          .map((item) => MajlisScheduleItem.fromJson(JsonHelper.asMap(item)))
          .toList(),
    );
  }
}

class MajlisScheduleItem {
  MajlisScheduleItem({
    required this.id,
    required this.startTime,
    required this.subjectName,
    required this.teacherName,
  });

  final int id;
  final String startTime;
  final String subjectName;
  final String teacherName;

  factory MajlisScheduleItem.fromJson(Map<String, dynamic> json) {
    return MajlisScheduleItem(
      id: JsonHelper.asInt(json['id']),
      startTime: JsonHelper.asString(json['start_time'], fallback: '-'),
      subjectName: JsonHelper.asString(json['subject_name'], fallback: '-'),
      teacherName: JsonHelper.asString(json['teacher_name'], fallback: '-'),
    );
  }
}

class MajlisFinance {
  MajlisFinance({
    required this.applicable,
    required this.invoices,
    required this.summary,
  });

  final bool applicable;
  final List<MajlisInvoice> invoices;
  final MajlisFinanceSummary summary;

  factory MajlisFinance.fromJson(Map<String, dynamic> json) {
    return MajlisFinance(
      applicable: json['applicable'] == true,
      invoices: JsonHelper.asList(json['invoices'])
          .map((item) => MajlisInvoice.fromJson(JsonHelper.asMap(item)))
          .toList(),
      summary: MajlisFinanceSummary.fromJson(JsonHelper.asMap(json['summary'])),
    );
  }
}

class MajlisInvoice {
  MajlisInvoice({
    required this.id,
    required this.invoiceNumber,
    required this.studentName,
    required this.feeType,
    required this.remainingAmount,
    required this.statusLabel,
  });

  final int id;
  final String invoiceNumber;
  final String studentName;
  final String feeType;
  final num remainingAmount;
  final String statusLabel;

  factory MajlisInvoice.fromJson(Map<String, dynamic> json) {
    return MajlisInvoice(
      id: JsonHelper.asInt(json['id']),
      invoiceNumber: JsonHelper.asString(json['invoice_number'], fallback: '-'),
      studentName: JsonHelper.asString(json['student_name'], fallback: '-'),
      feeType: JsonHelper.asString(json['fee_type'], fallback: '-'),
      remainingAmount: JsonHelper.asDouble(json['remaining_amount']),
      statusLabel: JsonHelper.asString(json['status_label'], fallback: '-'),
    );
  }
}

class MajlisFinanceSummary {
  MajlisFinanceSummary({
    required this.totalAmount,
    required this.paidAmount,
    required this.remainingAmount,
    required this.unpaidCount,
  });

  final num totalAmount;
  final num paidAmount;
  final num remainingAmount;
  final int unpaidCount;

  double get paidProgress {
    if (totalAmount <= 0) return 0;
    return (paidAmount / totalAmount).clamp(0, 1).toDouble();
  }

  factory MajlisFinanceSummary.fromJson(Map<String, dynamic> json) {
    return MajlisFinanceSummary(
      totalAmount: JsonHelper.asDouble(json['total_amount']),
      paidAmount: JsonHelper.asDouble(json['paid_amount']),
      remainingAmount: JsonHelper.asDouble(json['remaining_amount']),
      unpaidCount: JsonHelper.asInt(json['unpaid_count']),
    );
  }
}
