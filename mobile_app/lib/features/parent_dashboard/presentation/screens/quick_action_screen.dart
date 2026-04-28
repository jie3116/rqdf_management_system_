import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../../core/theme/app_colors.dart';
import '../../../../../core/utils/app_date_formatter.dart';
import '../../../../../core/utils/currency_formatter.dart';
import '../../../../../core/utils/json_helper.dart';
import '../../../../../shared/models/view_state.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../../../../shared/widgets/app_empty_state.dart';
import '../../../../../shared/widgets/app_error_state.dart';
import '../../../../../shared/widgets/app_loading_view.dart';
import '../../../../../shared/widgets/section_title.dart';
import '../../data/models/quick_action_model.dart';
import '../providers/quick_action_provider.dart';

class QuickActionScreenArgs {
  QuickActionScreenArgs({required this.action, this.childId});
  final QuickActionModel action;
  final int? childId;
}

class QuickActionScreen extends StatelessWidget {
  const QuickActionScreen({super.key, required this.args});

  static const String routeName = '/quick-action';
  final QuickActionScreenArgs args;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        surfaceTintColor: AppColors.background,
        title: Text(
          args.action.label,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      body: QuickActionContent(action: args.action, childId: args.childId),
    );
  }
}

class QuickActionContent extends StatefulWidget {
  const QuickActionContent({super.key, required this.action, this.childId});
  final QuickActionModel action;
  final int? childId;

  @override
  State<QuickActionContent> createState() => _QuickActionContentState();
}

class _QuickActionContentState extends State<QuickActionContent> {
  String? _selectedPeriodType;
  int? _selectedAcademicYearId;
  String? _selectedYearName;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void didUpdateWidget(covariant QuickActionContent oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.childId != widget.childId ||
        oldWidget.action.key != widget.action.key) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    }
  }

  Future<void> _load() {
    if (widget.childId == null || widget.childId! <= 0) return Future.value();
    final query = _supportsPeriod(widget.action.key)
        ? <String, dynamic>{
            if ((_selectedPeriodType ?? '').isNotEmpty)
              'period_type': _selectedPeriodType,
            if ((_selectedPeriodType ?? 'SEMESTER') == 'SEMESTER' &&
                _selectedAcademicYearId != null)
              'academic_year_id': _selectedAcademicYearId,
            if ((_selectedPeriodType ?? '') == 'YEAR' &&
                (_selectedYearName ?? '').isNotEmpty)
              'year_name': _selectedYearName,
          }
        : null;
    return context
        .read<QuickActionProvider>()
        .load(action: widget.action, childId: widget.childId, query: query)
        .then((_) {
      if (!mounted) return;
      final payload = context.read<QuickActionProvider>().result?.payload;
      if (payload == null) return;
      _syncPeriodFromPayload(payload);
    });
  }

  bool _supportsPeriod(String actionKey) {
    final key = actionKey.toLowerCase();
    return key == 'nilai' || key == 'absensi' || key == 'perilaku';
  }

  void _syncPeriodFromPayload(Map<String, dynamic> payload) {
    if (!_supportsPeriod(widget.action.key)) return;
    final reportPeriod = JsonHelper.asMap(payload['report_period']);
    if (reportPeriod.isEmpty) return;
    _selectedPeriodType = JsonHelper.asString(
      reportPeriod['period_type'],
      fallback: _selectedPeriodType ?? 'SEMESTER',
    );
    final yearId = JsonHelper.asInt(reportPeriod['academic_year_id']);
    _selectedAcademicYearId = yearId > 0 ? yearId : null;
    _selectedYearName = JsonHelper.asString(
      reportPeriod['year_name'],
      fallback: _selectedYearName ?? '',
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<QuickActionProvider>();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          _Banner(action: widget.action),
          const SizedBox(height: 18),
          if (widget.childId == null || widget.childId! <= 0)
            const AppEmptyState(
              title: 'Anak Belum Dipilih',
              subtitle: 'Pilih data anak terlebih dahulu dari tab Home.',
            )
          else if (provider.state == ViewState.loading)
            const SizedBox(
              height: 220,
              child: AppLoadingView(message: 'Memuat data fitur...'),
            )
          else if (provider.state == ViewState.error)
            AppErrorState(
              message: provider.errorMessage ?? 'Terjadi kesalahan.',
              onRetry: _load,
            )
          else if (provider.result != null)
            _Renderer(
              action: widget.action,
              payload: provider.result!.payload,
              selectedPeriodType: _selectedPeriodType,
              selectedAcademicYearId: _selectedAcademicYearId,
              selectedYearName: _selectedYearName,
              onPeriodTypeChanged: _supportsPeriod(widget.action.key)
                  ? (value) {
                      setState(() {
                        _selectedPeriodType = value;
                        _selectedAcademicYearId = null;
                        _selectedYearName = null;
                      });
                      _load();
                    }
                  : null,
              onSemesterChanged: _supportsPeriod(widget.action.key)
                  ? (value) {
                      setState(() => _selectedAcademicYearId = value);
                      _load();
                    }
                  : null,
              onYearNameChanged: _supportsPeriod(widget.action.key)
                  ? (value) {
                      setState(() => _selectedYearName = value);
                      _load();
                    }
                  : null,
            )
          else
            const AppErrorState(message: 'Data tidak tersedia.'),
        ],
      ),
    );
  }
}

class _Renderer extends StatelessWidget {
  const _Renderer({
    required this.action,
    required this.payload,
    this.selectedPeriodType,
    this.selectedAcademicYearId,
    this.selectedYearName,
    this.onPeriodTypeChanged,
    this.onSemesterChanged,
    this.onYearNameChanged,
  });
  final QuickActionModel action;
  final Map<String, dynamic> payload;
  final String? selectedPeriodType;
  final int? selectedAcademicYearId;
  final String? selectedYearName;
  final ValueChanged<String?>? onPeriodTypeChanged;
  final ValueChanged<int?>? onSemesterChanged;
  final ValueChanged<String?>? onYearNameChanged;

  @override
  Widget build(BuildContext context) {
    final key = action.key.toLowerCase();
    final accent = _accent(key);
    final student = JsonHelper.asMap(payload['student']);
    final supportsPeriod = key == 'nilai' || key == 'absensi' || key == 'perilaku';
    final period = JsonHelper.asMap(payload['report_period']);
    final options = JsonHelper.asMap(payload['report_period_options']);
    final periodType =
        selectedPeriodType ?? JsonHelper.asString(period['period_type'], fallback: 'SEMESTER');
    final semesterOptions = JsonHelper.asList(options['semester_options']);
    final yearOptions = JsonHelper.asList(options['year_options']);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StudentCard(student: student, accent: accent),
        if (supportsPeriod) ...[
          const SizedBox(height: 14),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Periode Laporan',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: periodType,
                  items: JsonHelper.asList(options['type_options']).map((item) {
                    final row = JsonHelper.asMap(item);
                    final value = JsonHelper.asString(row['key']);
                    final label = JsonHelper.asString(row['label'], fallback: value);
                    return DropdownMenuItem<String>(value: value, child: Text(label));
                  }).toList(),
                  onChanged: onPeriodTypeChanged,
                  decoration: const InputDecoration(labelText: 'Jenis Periode'),
                ),
                const SizedBox(height: 10),
                if (periodType == 'YEAR')
                  DropdownButtonFormField<String>(
                    initialValue: () {
                      final value =
                          selectedYearName ?? JsonHelper.asString(period['year_name']);
                      final allowed = yearOptions
                          .map((item) => JsonHelper.asString(JsonHelper.asMap(item)['key']))
                          .toSet();
                      return value.isNotEmpty && allowed.contains(value) ? value : null;
                    }(),
                    items: yearOptions.map((item) {
                      final row = JsonHelper.asMap(item);
                      final value = JsonHelper.asString(row['key']);
                      return DropdownMenuItem<String>(
                        value: value,
                        child: Text(JsonHelper.asString(row['label'], fallback: value)),
                      );
                    }).toList(),
                    onChanged: onYearNameChanged,
                    decoration: const InputDecoration(labelText: 'Tahun Ajaran'),
                  )
                else
                  DropdownButtonFormField<int>(
                    initialValue: () {
                      final fromPayload = JsonHelper.asInt(period['academic_year_id']);
                      final candidate =
                          selectedAcademicYearId ?? (fromPayload > 0 ? fromPayload : null);
                      final allowed = semesterOptions
                          .map((item) => JsonHelper.asInt(JsonHelper.asMap(item)['id']))
                          .toSet();
                      return candidate != null && allowed.contains(candidate)
                          ? candidate
                          : null;
                    }(),
                    items: semesterOptions.map((item) {
                      final row = JsonHelper.asMap(item);
                      final id = JsonHelper.asInt(row['id']);
                      return DropdownMenuItem<int>(
                        value: id,
                        child: Text(JsonHelper.asString(row['label'], fallback: '$id')),
                      );
                    }).toList(),
                    onChanged: onSemesterChanged,
                    decoration: const InputDecoration(labelText: 'Semester'),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 14),
        if (key == 'pengumuman') ..._announcementSections(payload, accent),
        if (key == 'keuangan') ..._financeSections(payload, accent),
        if (key == 'tahfidz') ..._memorizationSections(payload, accent),
        if (key == 'nilai') ..._gradeSections(payload, accent),
        if (key == 'jadwal') ..._scheduleSections(payload, accent),
        if (key == 'absensi') ..._attendanceSections(payload, accent),
        if (key == 'perilaku') ..._behaviorSections(payload, accent),
      ],
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.action});
  final QuickActionModel action;

  @override
  Widget build(BuildContext context) {
    final accent = _accent(action.key);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_dark(accent), accent],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: accent.withValues(alpha: 0.20),
            blurRadius: 24,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Icon(_icon(action.key), color: Colors.white),
          ),
          const SizedBox(height: 16),
          Text(
            action.label,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            _description(action.key),
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withValues(alpha: 0.84),
                  height: 1.45,
                ),
          ),
        ],
      ),
    );
  }
}

class _StudentCard extends StatelessWidget {
  const _StudentCard({required this.student, required this.accent});
  final Map<String, dynamic> student;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final name = JsonHelper.asString(
      student['full_name'] ?? student['name'],
      fallback: '-',
    );
    final className = JsonHelper.asString(
      student['current_class_name'] ?? student['class_name'],
      fallback: '-',
    );
    final nis = JsonHelper.asString(student['nis'], fallback: '-');

    return AppCard(
      padding: const EdgeInsets.all(18),
      child: Row(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Center(
              child: Text(
                name.isNotEmpty ? name[0].toUpperCase() : 'S',
                style: TextStyle(
                  color: _dark(accent),
                  fontWeight: FontWeight.w800,
                  fontSize: 20,
                ),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Siswa aktif',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'NIS $nis - $className',
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

List<Widget> _announcementSections(Map<String, dynamic> payload, Color accent) {
  final items = JsonHelper.asList(payload['items']);
  final unreadCount = JsonHelper.asInt(payload['unread_count']);

  return [
    if (unreadCount > 0)
      _InfoCard(
        accent: accent,
        title: '$unreadCount pengumuman belum dibaca',
        subtitle: 'Pengumuman terbaru sekolah ditampilkan di sini.',
      ),
    if (unreadCount > 0) const SizedBox(height: 14),
    const SectionTitle(title: 'Daftar Pengumuman'),
    const SizedBox(height: 10),
    _CardList(
      items: items,
      emptySubtitle: 'Belum ada pengumuman untuk profil ini.',
      titleBuilder: (row) => JsonHelper.asString(row['title'], fallback: '-'),
      subtitleBuilder: (row) =>
          '${JsonHelper.asString(row['author_label'], fallback: 'Sistem')} • ${AppDateFormatter.shortDate(JsonHelper.asString(row['created_at']))}\n${JsonHelper.asString(row['content'], fallback: '-')}',
      badgeBuilder: (row) => row['is_unread'] == true ? 'Baru' : '',
      accent: accent,
    ),
  ];
}

List<Widget> _financeSections(Map<String, dynamic> payload, Color accent) {
  final summary = JsonHelper.asMap(payload['summary']);
  final items = JsonHelper.asList(payload['invoices']);
  return [
    _MetricGrid(
      title: 'Ringkasan Keuangan',
      accent: accent,
      items: [
        MapEntry('Total', CurrencyFormatter.rupiah(JsonHelper.asDouble(summary['total_amount']))),
        MapEntry('Dibayar', CurrencyFormatter.rupiah(JsonHelper.asDouble(summary['paid_amount']))),
        MapEntry('Sisa', CurrencyFormatter.rupiah(JsonHelper.asDouble(summary['remaining_amount']))),
        MapEntry('Belum lunas', '${JsonHelper.asInt(summary['unpaid_count'])} invoice'),
      ],
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Daftar Tagihan'),
    const SizedBox(height: 10),
    _CardList(
      items: items,
      emptySubtitle: 'Belum ada data tagihan untuk anak ini.',
      titleBuilder: (row) => JsonHelper.asString(row['invoice_number'], fallback: 'Invoice'),
      subtitleBuilder: (row) =>
          'Jenis ${JsonHelper.asString(row['fee_type'], fallback: '-')}\n${AppDateFormatter.dateLabel(JsonHelper.asString(row['created_at']))} • Jatuh tempo ${AppDateFormatter.shortDate(JsonHelper.asString(row['due_date']))}\nSisa ${CurrencyFormatter.rupiah(JsonHelper.asDouble(row['remaining_amount']))}',
      badgeBuilder: (row) => JsonHelper.asString(row['status_label'], fallback: '-'),
      accent: accent,
    ),
  ];
}

List<Widget> _memorizationSections(Map<String, dynamic> payload, Color accent) {
  final summary = JsonHelper.asMap(payload['summary']);
  return [
    _MetricGrid(
      title: 'Ringkasan Tahfidz',
      accent: accent,
      items: [
        MapEntry('Total juz', '${JsonHelper.asInt(summary['total_juz'])}'),
        MapEntry('Surah terakhir', JsonHelper.asString(summary['last_surah'], fallback: '-')),
        MapEntry('Ayat terakhir', JsonHelper.asString(summary['last_ayat'], fallback: '-')),
        MapEntry('Progress', JsonHelper.asString(summary['last_target_text'], fallback: '-')),
      ],
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Riwayat Setoran Hafalan'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['records']),
      emptySubtitle: 'Belum ada data hafalan.',
      titleBuilder: (row) =>
          '${JsonHelper.asString(row['surah'], fallback: '-') } (${JsonHelper.asString(row['ayat_start'], fallback: '?')}-${JsonHelper.asString(row['ayat_end'], fallback: '?')})',
      subtitleBuilder: (row) =>
          'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\nJenis ${JsonHelper.asString(row['type_label'], fallback: '-')}',
      badgeBuilder: (row) => JsonHelper.asString(row['score'], fallback: '-'),
      accent: accent,
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Riwayat Setoran Bacaan'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['recitation_records']),
      emptySubtitle: 'Belum ada data setoran bacaan.',
      titleBuilder: (row) => JsonHelper.asString(row['material_text'], fallback: '-'),
      subtitleBuilder: (row) =>
          'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\nSumber ${JsonHelper.asString(row['recitation_source_label'], fallback: '-')}',
      badgeBuilder: (row) => JsonHelper.asString(row['score'], fallback: '-'),
      accent: accent,
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Evaluasi Tahfidz'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['evaluations']),
      emptySubtitle: 'Belum ada evaluasi tahfidz.',
      titleBuilder: (row) => JsonHelper.asString(row['period_type_label'], fallback: 'Evaluasi'),
      subtitleBuilder: (row) =>
          'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\n${JsonHelper.asString(row['notes'], fallback: '-')}',
      badgeBuilder: (row) => JsonHelper.asString(row['score'], fallback: '-'),
      accent: accent,
    ),
  ];
}

List<Widget> _gradeSections(Map<String, dynamic> payload, Color accent) {
  final year = JsonHelper.asMap(payload['academic_year']);
  return [
    _MetricGrid(
      title: 'Ringkasan Akademik',
      accent: accent,
      items: [
        MapEntry('Tahun ajaran', JsonHelper.asString(year['name'], fallback: '-')),
        MapEntry('Semester', JsonHelper.asString(year['semester'], fallback: '-')),
        MapEntry('Ringkasan mapel', '${JsonHelper.asList(payload['summary']).length}'),
        MapEntry('Detail nilai', '${JsonHelper.asList(payload['grades']).length}'),
      ],
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Detail Nilai'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['grades']),
      emptySubtitle: 'Data nilai belum tersedia.',
      titleBuilder: (row) => JsonHelper.asString(row['subject_name'], fallback: '-'),
      subtitleBuilder: (row) =>
          'Tipe ${JsonHelper.asString(row['type_label'], fallback: '-')}\n${AppDateFormatter.dateLabel(JsonHelper.asString(row['created_at']))}\n${JsonHelper.asString(row['notes'], fallback: '-')}',
      badgeBuilder: (row) => JsonHelper.asString(row['score'], fallback: '-'),
      accent: accent,
    ),
  ];
}

List<Widget> _scheduleSections(Map<String, dynamic> payload, Color accent) {
  final todayName = JsonHelper.asString(payload['today_name'], fallback: 'Hari ini');
  return [
    _InfoCard(
      accent: accent,
      title: 'Jadwal hari ini: $todayName',
      subtitle: '${JsonHelper.asList(payload['today_items']).length} item terjadwal.',
    ),
    const SizedBox(height: 14),
    const SectionTitle(title: 'Jadwal Mingguan'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['days']),
      emptySubtitle: 'Belum ada jadwal mingguan.',
      titleBuilder: (row) => JsonHelper.asString(row['day'], fallback: 'Hari'),
      subtitleBuilder: (row) => JsonHelper.asList(row['items']).isEmpty
          ? 'Libur'
          : JsonHelper.asList(row['items'])
              .map((item) {
                final entry = JsonHelper.asMap(item);
                return '${JsonHelper.asString(entry['start_time'], fallback: '--:--')} ${JsonHelper.asString(entry['subject_name'], fallback: '-')}';
              })
              .join('\n'),
      badgeBuilder: (row) => '${JsonHelper.asList(row['items']).length} item',
      accent: accent,
    ),
  ];
}

List<Widget> _attendanceSections(Map<String, dynamic> payload, Color accent) {
  final recap = JsonHelper.asMap(payload['recap']);
  final boardingReacp = JsonHelper.asMap(payload['boarding_recap']);
  return [
    _MetricGrid(
      title: 'Absensi Kelas',
      accent: accent,
      items: [
        MapEntry('Hadir', '${JsonHelper.asInt(recap['hadir'])}'),
        MapEntry('Sakit', '${JsonHelper.asInt(recap['sakit'])}'),
        MapEntry('Izin', '${JsonHelper.asInt(recap['izin'])}'),
        MapEntry('Alpa', '${JsonHelper.asInt(recap['alpa'])}'),
      ],
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Riwayat Absensi Kelas'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['records']),
      emptySubtitle: 'Belum ada data absensi kelas.',
      titleBuilder: (row) => JsonHelper.asString(row['status_label'], fallback: '-'),
      subtitleBuilder: (row) =>
          'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\nGuru ${JsonHelper.asString(row['teacher_name'], fallback: '-')}',
      badgeBuilder: (row) => JsonHelper.asString(row['status_label'], fallback: '-'),
      accent: accent,
    ),
    if (payload['is_boarding_student'] == true) ...[
      const SizedBox(height: 20),
      _MetricGrid(
        title: 'Absensi Asrama',
        accent: accent,
        items: [
          MapEntry('Hadir', '${JsonHelper.asInt(boardingReacp['hadir'])}'),
          MapEntry('Sakit', '${JsonHelper.asInt(boardingReacp['sakit'])}'),
          MapEntry('Izin', '${JsonHelper.asInt(boardingReacp['izin'])}'),
          MapEntry('Alpa', '${JsonHelper.asInt(boardingReacp['alpa'])}'),
        ],
      ),
      const SizedBox(height: 20),
      const SectionTitle(title: 'Riwayat Absensi Asrama'),
      const SizedBox(height: 10),
      _CardList(
        items: JsonHelper.asList(payload['boarding_records']),
        emptySubtitle: 'Belum ada data absensi asrama.',
        titleBuilder: (row) => JsonHelper.asString(row['activity_name'], fallback: '-'),
        subtitleBuilder: (row) =>
            'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\n${JsonHelper.asString(row['notes'], fallback: '-')}',
        badgeBuilder: (row) => JsonHelper.asString(row['status_label'], fallback: '-'),
        accent: accent,
      ),
    ],
  ];
}

List<Widget> _behaviorSections(Map<String, dynamic> payload, Color accent) {
  final summary = JsonHelper.asMap(payload['summary']);
  final matrix = JsonHelper.asMap(payload['matrix']);
  final positiveRows = JsonHelper.asList(matrix['positive']);
  final negativeRows = JsonHelper.asList(matrix['negative']);
  return [
    _MetricGrid(
      title: 'Ringkasan Perilaku',
      accent: accent,
      items: [
        MapEntry('Total poin', '${JsonHelper.asInt(summary['point_total'])}'),
        MapEntry('Pelanggaran', '${JsonHelper.asInt(summary['violation_count'])}'),
        MapEntry('Laporan guru', '${JsonHelper.asInt(summary['behavior_report_count'])}'),
        MapEntry('Pertemuan', '${JsonHelper.asInt(summary['total_meetings'])}'),
      ],
    ),
    const SizedBox(height: 20),
    _InfoCard(
      accent: accent,
      title: 'Catatan wali kelas',
      subtitle: JsonHelper.asString(summary['latest_note'], fallback: '-'),
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Sikap Yang Harus Dipertahankan'),
    const SizedBox(height: 10),
    _BehaviorMatrixCards(rows: positiveRows),
    const SizedBox(height: 16),
    const SectionTitle(title: 'Sikap Yang Harus Dihindari'),
    const SizedBox(height: 10),
    _BehaviorMatrixCards(rows: negativeRows),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Laporan Perilaku Guru'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['reports']),
      emptySubtitle: 'Belum ada laporan perilaku dari guru.',
      titleBuilder: (row) => JsonHelper.asString(
        row['indicator_label'] ?? row['title'],
        fallback: '-',
      ),
      subtitleBuilder: (row) =>
          '${JsonHelper.asString(row['teacher_name'], fallback: '-')}\n${JsonHelper.asString(row['description'], fallback: '-')}',
      badgeBuilder: (row) => row['is_yes'] == true ? 'YA' : 'TIDAK',
      accent: accent,
    ),
    const SizedBox(height: 20),
    const SectionTitle(title: 'Catatan Kedisiplinan'),
    const SizedBox(height: 10),
    _CardList(
      items: JsonHelper.asList(payload['violations']),
      emptySubtitle: 'Bersih, tidak ada pelanggaran.',
      titleBuilder: (row) => JsonHelper.asString(row['description'], fallback: '-'),
      subtitleBuilder: (row) =>
          'Tanggal ${JsonHelper.asString(row['date'], fallback: '-')}\nSanksi ${JsonHelper.asString(row['sanction'], fallback: '-')}',
      badgeBuilder: (row) => '+${JsonHelper.asInt(row['points'])}',
      accent: accent,
    ),
  ];
}

class _BehaviorMatrixCards extends StatelessWidget {
  const _BehaviorMatrixCards({required this.rows});

  final List<dynamic> rows;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return const AppEmptyState(
        title: 'Belum Ada Data',
        subtitle: 'Data indikator perilaku belum tersedia.',
      );
    }
    return Column(
      children: rows.map((item) {
        final row = JsonHelper.asMap(item);
        final category = JsonHelper.asString(row['category_key'], fallback: 'TP');
        return AppCard(
          margin: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  JsonHelper.asString(row['label'], fallback: '-'),
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F1FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  category,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF1D4ED8),
                  ),
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({
    required this.title,
    required this.accent,
    required this.items,
  });

  final String title;
  final Color accent;
  final List<MapEntry<String, String>> items;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionTitle(title: title),
          const SizedBox(height: 12),
          GridView.builder(
            itemCount: items.length,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              mainAxisExtent: 78,
            ),
            itemBuilder: (_, index) => Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FBFF),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.borderSoft),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    items[index].key,
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    items[index].value,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      color: _dark(accent),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CardList extends StatelessWidget {
  const _CardList({
    required this.items,
    required this.emptySubtitle,
    required this.titleBuilder,
    required this.subtitleBuilder,
    required this.badgeBuilder,
    required this.accent,
  });

  final List<dynamic> items;
  final String emptySubtitle;
  final String Function(Map<String, dynamic>) titleBuilder;
  final String Function(Map<String, dynamic>) subtitleBuilder;
  final String Function(Map<String, dynamic>) badgeBuilder;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return AppEmptyState(
        title: 'Belum Ada Data',
        subtitle: emptySubtitle,
      );
    }

    return Column(
      children: items.map((item) {
        final row = JsonHelper.asMap(item);
        final badge = badgeBuilder(row);
        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: AppCard(
            padding: const EdgeInsets.all(18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        titleBuilder(row),
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: 15.5,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        subtitleBuilder(row),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                if (badge.isNotEmpty) ...[
                  const SizedBox(width: 10),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      badge,
                      style: TextStyle(
                        color: _dark(accent),
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.accent,
    required this.title,
    required this.subtitle,
  });

  final Color accent;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(Icons.info_outline_rounded, color: accent),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

IconData _icon(String key) => {
      'pengumuman': Icons.campaign_rounded,
      'keuangan': Icons.account_balance_wallet_rounded,
      'tahfidz': Icons.menu_book_rounded,
      'nilai': Icons.bar_chart_rounded,
      'absensi': Icons.fact_check_rounded,
      'jadwal': Icons.calendar_month_rounded,
      'perilaku': Icons.shield_outlined,
    }[key.toLowerCase()] ??
    Icons.apps_rounded;

Color _accent(String key) => {
      'pengumuman': const Color(0xFFEF4444),
      'keuangan': const Color(0xFFF59E0B),
      'tahfidz': AppColors.success,
      'nilai': AppColors.accentBlue,
      'absensi': AppColors.accentTeal,
      'jadwal': const Color(0xFF7C3AED),
      'perilaku': AppColors.danger,
    }[key.toLowerCase()] ??
    AppColors.primary;

Color _dark(Color color) {
  final hsl = HSLColor.fromColor(color);
  return hsl
      .withLightness((hsl.lightness - 0.14).clamp(0.0, 1.0))
      .toColor();
}

String _description(String key) => {
      'pengumuman':
          'Lihat informasi terbaru sekolah yang relevan untuk profil anak.',
      'keuangan':
          'Pantau tagihan, progres pembayaran, dan invoice yang perlu ditindaklanjuti.',
      'tahfidz':
          'Lihat hafalan, setoran bacaan, dan evaluasi tahfidz dalam satu layar.',
      'nilai':
          'Tinjau ringkasan akademik, nilai rata-rata, dan detail penilaian.',
      'absensi':
          'Periksa absensi kelas dan absensi asrama bila anak tinggal di asrama.',
      'jadwal': 'Pantau jadwal mingguan dan agenda pelajaran harian siswa.',
      'perilaku':
          'Lihat laporan perilaku guru dan catatan kedisiplinan siswa.',
    }[key.toLowerCase()] ??
    'Detail fitur ditampilkan di halaman ini.';
