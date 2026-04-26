import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/constants/quran_options.dart';
import '../../../../core/network/api_exception.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_date_formatter.dart';
import '../../../../core/utils/json_helper.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/app_empty_state.dart';
import '../../../../shared/widgets/app_error_state.dart';
import '../../../../shared/widgets/app_loading_view.dart';
import '../../../../shared/widgets/section_title.dart';
import '../../data/repositories/teacher_action_repository.dart';

class TeacherModuleArgs {
  TeacherModuleArgs({
    required this.key,
    required this.title,
    this.classId,
    this.participantKey,
  });

  final String key;
  final String title;
  final int? classId;
  final String? participantKey;
}

class TeacherModuleScreen extends StatefulWidget {
  const TeacherModuleScreen({super.key, required this.args});

  static const routeName = '/teacher-module';
  final TeacherModuleArgs args;

  @override
  State<TeacherModuleScreen> createState() => _TeacherModuleScreenState();
}

class _TeacherModuleScreenState extends State<TeacherModuleScreen> {
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  Map<String, dynamic>? _payload;
  int? _selectedClassId;
  String? _selectedParticipantKey;
  String? _selectedChoice;
  String? _selectedExtraChoice;
  bool _flag = false;

  final _titleController = TextEditingController();
  final _contentController = TextEditingController();
  final _notesController = TextEditingController();
  final _startSurahController = TextEditingController();
  final _endSurahController = TextEditingController();
  final _ayatStartController = TextEditingController();
  final _ayatEndController = TextEditingController();
  final _bookNameController = TextEditingController();
  final _pageStartController = TextEditingController();
  final _pageEndController = TextEditingController();
  final _periodLabelController = TextEditingController();
  final _questionDetailsController = TextEditingController();
  final _dateController = TextEditingController();
  final _followUpDateController = TextEditingController();
  final _actionPlanController = TextEditingController();
  final _queryController = TextEditingController();
  final List<_EvaluationQuestionInput> _evaluationQuestions = [];

  final Map<String, int> _counters = {
    'tajwid_errors': 0,
    'makhraj_errors': 0,
    'tahfidz_errors': 0,
    'harakat_errors': 0,
  };

  @override
  void initState() {
    super.initState();
    _selectedClassId = widget.args.classId;
    _selectedParticipantKey = widget.args.participantKey;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    _notesController.dispose();
    _startSurahController.dispose();
    _endSurahController.dispose();
    _ayatStartController.dispose();
    _ayatEndController.dispose();
    _bookNameController.dispose();
    _pageStartController.dispose();
    _pageEndController.dispose();
    _periodLabelController.dispose();
    _questionDetailsController.dispose();
    _dateController.dispose();
    _followUpDateController.dispose();
    _actionPlanController.dispose();
    _queryController.dispose();
    for (final item in _evaluationQuestions) {
      item.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final payload = await context.read<TeacherActionRepository>().load(
        key: widget.args.key,
        query: {
          if (_selectedClassId != null) 'class_id': _selectedClassId,
          if ((widget.args.key == 'grade-history' ||
                  widget.args.key == 'attendance-history') &&
              (_selectedParticipantKey ?? '').isNotEmpty)
            'participant': _selectedParticipantKey,
          if (widget.args.key == 'input-behavior' &&
              _queryController.text.trim().isNotEmpty)
            'q': _queryController.text.trim(),
        },
      );
      _hydrate(payload);
      if (!mounted) return;
      setState(() {
        _payload = payload;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Gagal memuat ${widget.args.title}.';
        _loading = false;
      });
    }
  }

  void _hydrate(Map<String, dynamic> payload) {
    _selectedClassId ??= JsonHelper.asInt(
      JsonHelper.asMap(payload['selected_class'])['id'],
    );
    if (widget.args.key == 'input-tahfidz') {
      _selectedParticipantKey ??= _firstKey(payload['participants']);
      _selectedChoice ??= _firstKey(payload['tahfidz_types']);
    } else if (widget.args.key == 'input-recitation') {
      _selectedParticipantKey ??= _firstKey(payload['participants']);
      _selectedChoice ??= _firstKey(payload['recitation_sources']);
    } else if (widget.args.key == 'input-evaluation') {
      _selectedParticipantKey ??= _firstKey(payload['participants']);
      _selectedChoice ??= _firstKey(payload['evaluation_periods']);
      _syncEvaluationPeriodLabel();
      if (_evaluationQuestions.isEmpty) {
        _addEvaluationQuestion();
      }
    } else if (widget.args.key == 'input-behavior') {
      _selectedExtraChoice ??= _firstId(payload['students']);
      _selectedChoice ??= _firstKey(payload['behavior_types']);
      if (_dateController.text.isEmpty) {
        _dateController.text =
            DateTime.now().toIso8601String().split('T').first;
      }
    } else if (widget.args.key == 'grade-history' ||
        widget.args.key == 'attendance-history') {
      _selectedParticipantKey ??=
          widget.args.participantKey ??
              JsonHelper.asString(payload['selected_participant_key']);
    }
  }

  String? _firstKey(dynamic list) {
    final items = JsonHelper.asList(list);
    if (items.isEmpty) return null;
    return JsonHelper.asString(JsonHelper.asMap(items.first)['key']);
  }

  String? _firstId(dynamic list) {
    final items = JsonHelper.asList(list);
    if (items.isEmpty) return null;
    return '${JsonHelper.asInt(JsonHelper.asMap(items.first)['id'])}';
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    try {
      await context.read<TeacherActionRepository>().submit(
            key: widget.args.key,
            body: _body(),
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${widget.args.title} berhasil disimpan.')),
      );
      _clearAfterSubmit();
      await _load();
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Map<String, dynamic> _body() {
    switch (widget.args.key) {
      case 'input-tahfidz':
        return {
          'class_id': _selectedClassId,
          'participant_key': _selectedParticipantKey,
          'type': _selectedChoice,
          'start_surah_name': _startSurahController.text.trim(),
          'end_surah_name': _endSurahController.text.trim(),
          'ayat_start': _ayatStartController.text.trim(),
          'ayat_end': _ayatEndController.text.trim(),
          'tajwid_errors': _counters['tajwid_errors'],
          'makhraj_errors': _counters['makhraj_errors'],
          'tahfidz_errors': _counters['tahfidz_errors'],
          'quality': _titleController.text.trim(),
          'notes': _notesController.text.trim(),
        };
      case 'input-recitation':
        return {
          'class_id': _selectedClassId,
          'participant_key': _selectedParticipantKey,
          'recitation_source': _selectedChoice,
          'start_surah_name': _startSurahController.text.trim(),
          'end_surah_name': _endSurahController.text.trim(),
          'ayat_start': _ayatStartController.text.trim(),
          'ayat_end': _ayatEndController.text.trim(),
          'book_name': _bookNameController.text.trim(),
          'page_start': _pageStartController.text.trim(),
          'page_end': _pageEndController.text.trim(),
          'tajwid_errors': _counters['tajwid_errors'],
          'makhraj_errors': _counters['makhraj_errors'],
          'notes': _notesController.text.trim(),
        };
      case 'input-evaluation':
        return {
          'class_id': _selectedClassId,
          'participant_key': _selectedParticipantKey,
          'period_type': _selectedChoice,
          'period_label': _periodLabelController.text.trim(),
          'question_details': _questionDetailsController.text.trim(),
          'questions': _evaluationQuestions
              .map(
                (item) => {
                  'surah': item.surahController.text.trim(),
                  'ayat': item.ayatController.text.trim(),
                  'score': item.scoreController.text.trim(),
                },
              )
              .toList(),
          'notes': _notesController.text.trim(),
        };
      case 'input-behavior':
        return {
          'class_id': _selectedClassId,
          'student_id': _selectedExtraChoice,
          'report_type': _selectedChoice,
          'report_date': _dateController.text.trim(),
          'title': _titleController.text.trim(),
          'description': _contentController.text.trim(),
          'action_plan': _actionPlanController.text.trim(),
          'follow_up_date': _followUpDateController.text.trim(),
          'is_resolved': _flag,
        };
      case 'class-announcements':
        return {
          'class_id': _selectedClassId,
          'title': _titleController.text.trim(),
          'content': _contentController.text.trim(),
          'is_active': _flag,
        };
      default:
        return const {};
    }
  }

  void _clearAfterSubmit() {
    _titleController.clear();
    _contentController.clear();
    _notesController.clear();
    _startSurahController.clear();
    _endSurahController.clear();
    _ayatStartController.clear();
    _ayatEndController.clear();
    _bookNameController.clear();
    _pageStartController.clear();
    _pageEndController.clear();
    _periodLabelController.clear();
    _questionDetailsController.clear();
    _actionPlanController.clear();
    _followUpDateController.clear();
    _flag = false;
    for (final item in _evaluationQuestions) {
      item.dispose();
    }
    _evaluationQuestions.clear();
    if (widget.args.key == 'input-evaluation') {
      _addEvaluationQuestion();
      _syncEvaluationPeriodLabel(forceReset: true);
    }
    for (final key in _counters.keys) {
      _counters[key] = 0;
    }
  }

  @override
  Widget build(BuildContext context) {
    final hideAppBarTitle = {
      'grade-history',
      'input-tahfidz',
      'input-recitation',
      'input-evaluation',
    }.contains(widget.args.key);
    final showBanner = !{
      'grade-history',
      'input-tahfidz',
      'input-recitation',
      'input-evaluation',
      'input-behavior',
    }.contains(widget.args.key);
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: hideAppBarTitle ? const SizedBox.shrink() : Text(widget.args.title),
      ),
      body: _loading
          ? const AppLoadingView(message: 'Memuat data...')
          : _error != null
              ? AppErrorState(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20),
                    children: [
                      if (showBanner) ...[
                        _Banner(title: widget.args.title),
                        const SizedBox(height: 18),
                      ],
                      ..._content(),
                    ],
                  ),
                ),
    );
  }

  List<Widget> _content() {
    switch (widget.args.key) {
      case 'input-tahfidz':
        return _inputTahfidz();
      case 'input-recitation':
        return _inputRecitation();
      case 'input-evaluation':
        return _inputEvaluation();
      case 'input-behavior':
        return _inputBehavior();
      case 'grade-history':
        return _gradeHistory();
      case 'attendance-history':
        return _attendanceHistory();
      case 'homeroom-students':
        return _homeroomStudents();
      case 'class-announcements':
        return _classAnnouncements();
      default:
        return const [
          AppEmptyState(
            title: 'Belum Tersedia',
            subtitle: 'Modul ini sedang disiapkan.',
          ),
        ];
    }
  }

  List<Widget> _inputTahfidz() {
    final payload = _payload ?? const <String, dynamic>{};
    return [
      _moduleHeaderCard(
        title: 'Input Tahfidz',
        subtitle: 'Pilih peserta, isi setoran surah dan ayat, lalu simpan hasil penilaian.',
        icon: Icons.menu_book_outlined,
      ),
      const SizedBox(height: 18),
      _classAndParticipant(
        classes: JsonHelper.asList(payload['classes']),
        participants: JsonHelper.asList(payload['participants']),
      ),
      const SizedBox(height: 12),
      _dropdown(
          'Jenis Setoran',
          _selectedChoice,
          JsonHelper.asList(payload['tahfidz_types']),
          (value) => setState(() => _selectedChoice = value)),
      const SizedBox(height: 12),
      _surahDropdown(_startSurahController, 'Surah awal'),
      const SizedBox(height: 12),
      _surahDropdown(_endSurahController, 'Surah akhir', allowEmpty: true),
      const SizedBox(height: 12),
      _surahInfo(_startSurahController.text),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(child: _text(_ayatStartController, 'Ayat awal', number: true)),
        const SizedBox(width: 10),
        Expanded(child: _text(_ayatEndController, 'Ayat akhir', number: true))
      ]),
      const SizedBox(height: 12),
      _text(_titleController, 'Kualitas'),
      const SizedBox(height: 12),
      _counterGroup(
          const ['tajwid_errors', 'makhraj_errors', 'tahfidz_errors']),
      const SizedBox(height: 12),
      _text(_notesController, 'Catatan'),
      const SizedBox(height: 12),
      AppButton(
          label: 'Simpan Setoran Tahfidz',
          onPressed: _submitting ? null : _submit,
          loading: _submitting,
          icon: Icons.save_outlined),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Riwayat Terbaru'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['recent_records']),
          (row) =>
              '${JsonHelper.asString(row['participant_name'])}\n${JsonHelper.asString(row['surah'])}',
          (row) {
            final ayatStart = JsonHelper.asString(row['ayat_start']);
            final ayatEnd = JsonHelper.asString(row['ayat_end']);
            final ayat = ayatStart.isNotEmpty && ayatEnd.isNotEmpty
                ? '\nAyat $ayatStart-$ayatEnd'
                : '';
            return '${JsonHelper.asString(row['type_label'])}$ayat';
          },
          (row) => JsonHelper.asString(row['score'])),
    ];
  }

  List<Widget> _inputRecitation() {
    final payload = _payload ?? const <String, dynamic>{};
    final source = _selectedChoice ?? 'QURAN';
    return [
      _moduleHeaderCard(
        title: 'Input Bacaan',
        subtitle: 'Catat bacaan Al-Qur\'an atau buku sumber sesuai materi yang diuji.',
        icon: Icons.auto_stories_outlined,
      ),
      const SizedBox(height: 18),
      _classAndParticipant(
        classes: JsonHelper.asList(payload['classes']),
        participants: JsonHelper.asList(payload['participants']),
      ),
      const SizedBox(height: 12),
      _dropdown(
          'Sumber Bacaan',
          _selectedChoice,
          JsonHelper.asList(payload['recitation_sources']),
          (value) => setState(() => _selectedChoice = value)),
      const SizedBox(height: 12),
      if (source == 'QURAN') ...[
        _surahDropdown(_startSurahController, 'Surah awal'),
        const SizedBox(height: 12),
        _surahDropdown(_endSurahController, 'Surah akhir', allowEmpty: true),
        const SizedBox(height: 12),
        _surahInfo(_startSurahController.text),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
              child: _text(_ayatStartController, 'Ayat awal', number: true)),
          const SizedBox(width: 10),
          Expanded(child: _text(_ayatEndController, 'Ayat akhir', number: true))
        ]),
      ] else ...[
        _bookDropdown(),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
              child: _text(_pageStartController, 'Halaman awal', number: true)),
          const SizedBox(width: 10),
          Expanded(
              child: _text(_pageEndController, 'Halaman akhir', number: true))
        ]),
      ],
      const SizedBox(height: 12),
      _counterGroup(const ['tajwid_errors', 'makhraj_errors']),
      const SizedBox(height: 12),
      _text(_notesController, 'Catatan'),
      const SizedBox(height: 12),
      AppButton(
          label: 'Simpan Setoran Bacaan',
          onPressed: _submitting ? null : _submit,
          loading: _submitting,
          icon: Icons.save_outlined),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Riwayat Terbaru'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['recent_records']),
          (row) => JsonHelper.asString(row['participant_name']),
          (row) {
            final sourceLabel = JsonHelper.asString(row['recitation_source_label']);
            final surah = JsonHelper.asString(row['surah']);
            final bookName = JsonHelper.asString(row['book_name']);
            final ayatStart = JsonHelper.asString(row['ayat_start']);
            final ayatEnd = JsonHelper.asString(row['ayat_end']);
            final pageStart = JsonHelper.asString(row['page_start']);
            final pageEnd = JsonHelper.asString(row['page_end']);
            if (bookName.isNotEmpty && bookName != '-') {
              final pages = pageStart.isNotEmpty && pageEnd.isNotEmpty
                  ? '\nHal. $pageStart-$pageEnd'
                  : '';
              return '$sourceLabel\n$bookName$pages';
            }
            final ayat = ayatStart.isNotEmpty && ayatEnd.isNotEmpty
                ? '\nAyat $ayatStart-$ayatEnd'
                : '';
            return '$sourceLabel\n$surah$ayat';
          },
          (row) => JsonHelper.asString(row['score'])),
    ];
  }

  List<Widget> _inputEvaluation() {
    final payload = _payload ?? const <String, dynamic>{};
    final periodLabelOptions = _evaluationPeriodLabelOptions(_selectedChoice);
    final averageScore = _evaluationAverageScore();
    return [
      _moduleHeaderCard(
        title: 'Input Evaluasi Tahfidz',
        subtitle: 'Tambahkan soal satu per satu. Nilai akhir dihitung dari rata-rata nilai setiap soal.',
        icon: Icons.fact_check_outlined,
      ),
      const SizedBox(height: 18),
      _classAndParticipant(
        classes: JsonHelper.asList(payload['classes']),
        participants: JsonHelper.asList(payload['participants']),
      ),
      const SizedBox(height: 12),
      _dropdown(
          'Periode Evaluasi',
          _selectedChoice,
          JsonHelper.asList(payload['evaluation_periods']),
          (value) => setState(() {
                _selectedChoice = value;
                _syncEvaluationPeriodLabel(forceReset: true);
              })),
      const SizedBox(height: 12),
      _dropdown(
        _evaluationPeriodLabelTitle(_selectedChoice),
        _periodLabelController.text.trim().isEmpty
            ? null
            : _periodLabelController.text.trim(),
        periodLabelOptions,
        (value) => setState(() {
          _periodLabelController.text = (value ?? '').trim();
        }),
      ),
      const SizedBox(height: 12),
      _text(_questionDetailsController, 'Keterangan materi uji',
          maxLines: 3),
      const SizedBox(height: 12),
      Row(
        children: [
          Expanded(
            child: Text(
              'Daftar Pertanyaan (${_evaluationQuestions.length})',
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 14,
              ),
            ),
          ),
          TextButton.icon(
            onPressed: () => setState(_addEvaluationQuestion),
            icon: const Icon(Icons.add_circle_outline),
            label: const Text('Tambah Pertanyaan'),
          ),
        ],
      ),
      const SizedBox(height: 8),
      ..._buildEvaluationQuestionFields(),
      const SizedBox(height: 12),
      AppCard(
        child: Row(
          children: [
            const Icon(Icons.calculate_outlined, color: AppColors.primary),
            const SizedBox(width: 12),
            const Expanded(
              child: Text(
                'Nilai akhir otomatis dihitung dari rata-rata semua soal.',
                style: TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 13,
                ),
              ),
            ),
            Text(
              averageScore ?? '-',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                fontSize: 18,
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      _text(_notesController, 'Catatan'),
      const SizedBox(height: 12),
      AppButton(
          label: 'Simpan Evaluasi',
          onPressed: _submitting ? null : _submit,
          loading: _submitting,
          icon: Icons.save_outlined),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Riwayat Evaluasi'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['recent_records']),
          (row) =>
              '${JsonHelper.asString(row['participant_name'])}\n${JsonHelper.asString(row['period_type_label'])}',
          (row) {
            final questionCount =
                JsonHelper.asString(row['question_count'], fallback: '0');
            final questionDetails = JsonHelper.asString(row['question_details']);
            final questionItems = JsonHelper.asList(row['question_items']);
            final previewLines = questionItems.take(4).map((item) {
              final question = JsonHelper.asMap(item);
              return '• ${JsonHelper.asString(question['surah'])} ayat ${JsonHelper.asString(question['ayat'])}: ${JsonHelper.asString(question['score'])}';
            }).where((item) => item.trim().isNotEmpty).join('\n');
            final moreCount =
                questionItems.length > 4 ? '\n+${questionItems.length - 4} soal lainnya' : '';
            final detailText = questionDetails.trim().isNotEmpty
                ? '\nMateri: $questionDetails'
                : '';
            final questionText =
                previewLines.isEmpty ? '' : '\n$previewLines$moreCount';
            return '${JsonHelper.asString(row['period_label'])}\n$questionCount pertanyaan$detailText$questionText';
          },
          (row) =>
              'Rata-rata ${JsonHelper.asString(row['score'])}'),
    ];
  }

  List<Widget> _buildEvaluationQuestionFields() {
    if (_evaluationQuestions.isEmpty) {
      return [
        const Text(
          'Tambahkan minimal satu pertanyaan evaluasi.',
          style: TextStyle(color: AppColors.textSecondary),
        ),
      ];
    }
    return List<Widget>.generate(_evaluationQuestions.length, (index) {
      final item = _evaluationQuestions[index];
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Soal ${index + 1}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                      ),
                    ),
                  ),
                  if (_evaluationQuestions.length > 1)
                    IconButton(
                      onPressed: () => setState(() {
                        final removed = _evaluationQuestions.removeAt(index);
                        removed.dispose();
                      }),
                      icon: const Icon(
                        Icons.delete_outline,
                        color: Colors.redAccent,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              _surahDropdown(item.surahController, 'Surah yang diuji'),
              const SizedBox(height: 10),
              _surahInfo(item.surahController.text),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: _text(
                      item.ayatController,
                      'Ayat',
                      number: true,
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _text(
                      item.scoreController,
                      'Nilai',
                      number: true,
                      onChanged: (_) => setState(() {}),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
    });
  }

  List<Widget> _inputBehavior() {
    final payload = _payload ?? const <String, dynamic>{};
    return [
      _classDropdown(JsonHelper.asList(payload['classes'])),
      const SizedBox(height: 12),
      _dropdown(
          'Siswa',
          _selectedExtraChoice,
          JsonHelper.asList(payload['students']).map((item) {
            final row = JsonHelper.asMap(item);
            return {
              'key': '${JsonHelper.asInt(row['id'])}',
              'label': row['name']
            };
          }).toList(),
          (value) => setState(() => _selectedExtraChoice = value)),
      const SizedBox(height: 12),
      _dropdown(
          'Tipe Laporan',
          _selectedChoice,
          JsonHelper.asList(payload['behavior_types']),
          (value) => setState(() => _selectedChoice = value)),
      const SizedBox(height: 12),
      _text(_dateController, 'Tanggal laporan (YYYY-MM-DD)'),
      const SizedBox(height: 12),
      _text(_titleController, 'Judul'),
      const SizedBox(height: 12),
      _text(_contentController, 'Deskripsi', maxLines: 3),
      const SizedBox(height: 12),
      _text(_actionPlanController, 'Rencana tindak lanjut'),
      const SizedBox(height: 12),
      _text(_followUpDateController, 'Tanggal follow up (YYYY-MM-DD)'),
      CheckboxListTile(
          value: _flag,
          contentPadding: EdgeInsets.zero,
          onChanged: (value) => setState(() => _flag = value ?? false),
          title: const Text('Sudah selesai')),
      const SizedBox(height: 12),
      AppButton(
          label: 'Simpan Laporan Perilaku',
          onPressed: _submitting ? null : _submit,
          loading: _submitting,
          icon: Icons.save_outlined),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Laporan Terbaru'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['recent_reports']),
          (row) =>
              '${JsonHelper.asString(row['student_name'])}\n${JsonHelper.asString(row['title'])}',
          (row) => JsonHelper.asString(row['report_type_label']),
          (row) => row['is_resolved'] == true ? 'Selesai' : 'Open'),
    ];
  }

  List<Widget> _gradeHistory() {
    final payload = _payload ?? const <String, dynamic>{};
    final selectedParticipant = JsonHelper.asMap(payload['selected_participant']);
    final selectedClass = JsonHelper.asMap(payload['selected_class']);
    return [
      if (selectedParticipant.isNotEmpty) ...[
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                JsonHelper.asString(selectedParticipant['display_name']),
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Kelas ${JsonHelper.asString(selectedClass['name'], fallback: '-')}',
                style: const TextStyle(color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
      ],
      const SectionTitle(title: 'Ringkasan Nilai (Rata-rata)'),
      const SizedBox(height: 10),
      ..._academicSummaryCards(JsonHelper.asList(payload['academic_summary_rows'])),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Riwayat Akademik'),
      const SizedBox(height: 10),
      ..._academicHistoryCards(JsonHelper.asList(payload['academic_grade_rows'])),
    ];
  }

  List<Widget> _attendanceHistory() {
    final payload = _payload ?? const <String, dynamic>{};
    return [
      _classDropdown(JsonHelper.asList(payload['classes']),
          reloadParticipant: true),
      const SizedBox(height: 12),
      _participantDropdown(JsonHelper.asList(payload['participants'])),
      const SizedBox(height: 18),
      _recapCard('Rekap Kelas', JsonHelper.asMap(payload['class_recap'])),
      const SizedBox(height: 12),
      _recapCard(
          'Rekap Peserta', JsonHelper.asMap(payload['participant_recap'])),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Absensi Kelas'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['class_attendances']),
          (row) => JsonHelper.asString(row['participant_name']),
          (row) => AppDateFormatter.shortDate(JsonHelper.asString(row['date'])),
          (row) => JsonHelper.asString(row['status_label'])),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Absensi Peserta'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['participant_attendances']),
          (row) => JsonHelper.asString(row['participant_name']),
          (row) => AppDateFormatter.shortDate(JsonHelper.asString(row['date'])),
          (row) => JsonHelper.asString(row['status_label'])),
    ];
  }

  List<Widget> _homeroomStudents() {
    final payload = _payload ?? const <String, dynamic>{};
    return [
      _classDropdown(JsonHelper.asList(payload['homeroom_classes'])),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Siswa Perwalian'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['students']),
          (row) => JsonHelper.asString(row['name']),
          (row) =>
              '${JsonHelper.asString(row['identifier_label'])}: ${JsonHelper.asString(row['identifier'])}',
          (_) => ''),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Peserta Majelis'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['majlis_participants']),
          (row) => JsonHelper.asString(row['name']),
          (row) =>
              '${JsonHelper.asString(row['identifier_label'])}: ${JsonHelper.asString(row['identifier'])}',
          (_) => ''),
    ];
  }

  List<Widget> _classAnnouncements() {
    final payload = _payload ?? const <String, dynamic>{};
    return [
      _classDropdown(JsonHelper.asList(payload['classes'])),
      const SizedBox(height: 12),
      _text(_titleController, 'Judul'),
      const SizedBox(height: 12),
      _text(_contentController, 'Isi pengumuman', maxLines: 4),
      CheckboxListTile(
          value: _flag,
          contentPadding: EdgeInsets.zero,
          onChanged: (value) => setState(() => _flag = value ?? false),
          title: const Text('Pengumuman aktif')),
      const SizedBox(height: 12),
      AppButton(
          label: 'Simpan Pengumuman',
          onPressed: _submitting ? null : _submit,
          loading: _submitting,
          icon: Icons.campaign_outlined),
      const SizedBox(height: 18),
      const SectionTitle(title: 'Pengumuman Terbaru'),
      const SizedBox(height: 10),
      ..._cards(
          JsonHelper.asList(payload['announcements']),
          (row) => JsonHelper.asString(row['title']),
          (row) =>
              '${JsonHelper.asString(row['class_name'])}\n${JsonHelper.asString(row['content'])}',
          (row) => row['is_active'] == true ? 'Aktif' : 'Nonaktif'),
    ];
  }

  Widget _classAndParticipant(
      {required List<dynamic> classes, required List<dynamic> participants}) {
    return Column(
      children: [
        _classDropdown(classes),
        const SizedBox(height: 12),
        _participantDropdown(participants),
      ],
    );
  }

  Widget _moduleHeaderCard({
    required String title,
    required String subtitle,
    required IconData icon,
  }) {
    return AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: AppColors.primary),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 17,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _classDropdown(List<dynamic> classes,
      {bool reloadParticipant = false}) {
    return DropdownButtonFormField<int>(
      initialValue: _selectedClassId != null && _selectedClassId! > 0
          ? _selectedClassId
          : null,
      items: classes.map((item) {
        final row = JsonHelper.asMap(item);
        return DropdownMenuItem<int>(
            value: JsonHelper.asInt(row['id']),
            child: Text(JsonHelper.asString(row['name'])));
      }).toList(),
      onChanged: (value) {
        setState(() {
          _selectedClassId = value;
          if (reloadParticipant) _selectedParticipantKey = null;
        });
        _load();
      },
      decoration: const InputDecoration(labelText: 'Kelas'),
    );
  }

  Widget _participantDropdown(List<dynamic> participants) {
    return _dropdown(
        'Peserta',
        _selectedParticipantKey,
        participants.map((item) {
          final row = JsonHelper.asMap(item);
          return {'key': row['key'], 'label': row['display_name']};
        }).toList(), (value) {
      setState(() => _selectedParticipantKey = value);
      if (widget.args.key == 'grade-history' ||
          widget.args.key == 'attendance-history') {
        _load();
      }
    });
  }

  Widget _dropdown(
    String label,
    String? value,
    List<dynamic> items,
    ValueChanged<String?> onChanged,
  ) {
    return DropdownButtonFormField<String>(
      initialValue: (value ?? '').isEmpty ? null : value,
      items: items.map((item) {
        final row = JsonHelper.asMap(item);
        final key = JsonHelper.asString(row['key']);
        final labelText = JsonHelper.asString(
          row['label'] ?? row['display_name'],
          fallback: key,
        );
        return DropdownMenuItem<String>(value: key, child: Text(labelText));
      }).toList(),
      onChanged: onChanged,
      decoration: InputDecoration(labelText: label),
    );
  }

  Widget _surahDropdown(
    TextEditingController controller,
    String label, {
    bool allowEmpty = false,
  }) {
    final currentValue = controller.text.trim();
    final selectedOption = kQuranSurahOptions.cast<SurahOption?>().firstWhere(
          (item) => item?.name == currentValue,
          orElse: () => null,
        );
    return _pickerField(
      label: label,
      value: selectedOption?.label ??
          (allowEmpty ? 'Pilih surah' : 'Tap untuk memilih surah'),
      onTap: () async {
        final selected = await _showPickerSheet(
          title: label,
          currentValue: currentValue,
          options: [
            if (allowEmpty)
              const _PickerOption(
                value: '',
                label: 'Kosongkan pilihan',
              ),
            ...kQuranSurahOptions.map(
              (item) => _PickerOption(
                value: item.name,
                label: item.label,
                subtitle: '${item.ayatCount} ayat',
              ),
            ),
          ],
        );
        if (!mounted || selected == null) return;
        setState(() {
          controller.text = selected.trim();
        });
      },
    );
  }

  Widget _bookDropdown() {
    final currentValue = _bookNameController.text.trim();
    return _pickerField(
      label: 'Nama kitab/buku',
      value: currentValue.isEmpty ? 'Tap untuk memilih buku' : currentValue,
      onTap: () async {
        final selected = await _showPickerSheet(
          title: 'Nama kitab/buku',
          currentValue: currentValue,
          options: kRecitationBookOptions
              .map((item) => _PickerOption(value: item, label: item))
              .toList(),
        );
        if (!mounted || selected == null) return;
        setState(() {
          _bookNameController.text = selected.trim();
        });
      },
    );
  }

  Widget _surahInfo(String surahName) {
    final option = kQuranSurahOptions.cast<SurahOption?>().firstWhere(
          (item) => item?.name == surahName,
          orElse: () => null,
        );
    final infoText = option == null
        ? 'Pilih surat Al-Qur\'an.'
        : 'Jumlah ayat surat ${option.name}: ${option.ayatCount} ayat';
    return Text(
      infoText,
      style: const TextStyle(
        color: AppColors.textSecondary,
        fontSize: 12,
      ),
    );
  }

  Widget _text(
    TextEditingController controller,
    String label, {
    bool number = false,
    int maxLines = 1,
    ValueChanged<String>? onChanged,
  }) {
    return TextField(
      controller: controller,
      keyboardType: number ? TextInputType.number : TextInputType.text,
      maxLines: maxLines,
      onChanged: onChanged,
      decoration: InputDecoration(labelText: label),
    );
  }

  Widget _pickerField({
    required String label,
    required String value,
    required Future<void> Function() onTap,
  }) {
    return InkWell(
      borderRadius: BorderRadius.circular(12),
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: const Icon(Icons.keyboard_arrow_down_rounded),
        ),
        child: Text(
          value,
          style: TextStyle(
            color: value.startsWith('Tap untuk') || value == 'Pilih surah'
                ? AppColors.textSecondary
                : AppColors.textPrimary,
          ),
        ),
      ),
    );
  }

  Future<String?> _showPickerSheet({
    required String title,
    required List<_PickerOption> options,
    String currentValue = '',
  }) {
    return showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) {
        var query = '';
        return StatefulBuilder(
          builder: (context, setModalState) {
            final filteredOptions = options.where((item) {
              if (query.trim().isEmpty) {
                return true;
              }
              final haystack =
                  '${item.label} ${item.subtitle ?? ''}'.toLowerCase();
              return haystack.contains(query.trim().toLowerCase());
            }).toList();
            return SafeArea(
              child: SizedBox(
                height: MediaQuery.of(context).size.height * 0.72,
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                      child: Column(
                        children: [
                          Text(
                            title,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            onChanged: (value) =>
                                setModalState(() => query = value),
                            decoration: const InputDecoration(
                              hintText: 'Cari pilihan...',
                              prefixIcon: Icon(Icons.search_rounded),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: ListView.builder(
                        itemCount: filteredOptions.length,
                        itemBuilder: (context, index) {
                          final item = filteredOptions[index];
                          return ListTile(
                            title: Text(item.label),
                            subtitle: item.subtitle == null
                                ? null
                                : Text(item.subtitle!),
                            trailing: item.value == currentValue
                                ? const Icon(
                                    Icons.check_circle_rounded,
                                    color: AppColors.primary,
                                  )
                                : null,
                            onTap: () => Navigator.of(context).pop(item.value),
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _counterGroup(List<String> keys) {
    return Column(
      children: keys.map((key) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              Expanded(child: Text(key.replaceAll('_', ' '))),
              IconButton(
                onPressed: () => setState(() {
                  final current = _counters[key] ?? 0;
                  _counters[key] = current > 0 ? current - 1 : 0;
                }),
                icon: const Icon(Icons.remove_circle_outline),
              ),
              Text('${_counters[key] ?? 0}'),
              IconButton(
                onPressed: () => setState(() {
                  _counters[key] = (_counters[key] ?? 0) + 1;
                }),
                icon: const Icon(Icons.add_circle_outline),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  void _addEvaluationQuestion() {
    _evaluationQuestions.add(_EvaluationQuestionInput());
  }

  List<Map<String, String>> _evaluationPeriodLabelOptions(String? periodType) {
    switch ((periodType ?? '').trim().toUpperCase()) {
      case 'BULANAN':
        return const [
          {'key': 'Januari', 'label': 'Januari'},
          {'key': 'Februari', 'label': 'Februari'},
          {'key': 'Maret', 'label': 'Maret'},
          {'key': 'April', 'label': 'April'},
          {'key': 'Mei', 'label': 'Mei'},
          {'key': 'Juni', 'label': 'Juni'},
          {'key': 'Juli', 'label': 'Juli'},
          {'key': 'Agustus', 'label': 'Agustus'},
          {'key': 'September', 'label': 'September'},
          {'key': 'Oktober', 'label': 'Oktober'},
          {'key': 'November', 'label': 'November'},
          {'key': 'Desember', 'label': 'Desember'},
        ];
      case 'TENGAH_SEMESTER':
        return const [
          {'key': 'Tengah Semester 1', 'label': 'Tengah Semester 1'},
          {'key': 'Tengah Semester 2', 'label': 'Tengah Semester 2'},
          {'key': 'Tengah Semester 3', 'label': 'Tengah Semester 3'},
          {'key': 'Tengah Semester 4', 'label': 'Tengah Semester 4'},
        ];
      case 'SEMESTER':
        return const [
          {'key': 'Semester 1', 'label': 'Semester 1'},
          {'key': 'Semester 2', 'label': 'Semester 2'},
        ];
      default:
        return const [];
    }
  }

  String _evaluationPeriodLabelTitle(String? periodType) {
    switch ((periodType ?? '').trim().toUpperCase()) {
      case 'BULANAN':
        return 'Pilih bulan';
      case 'TENGAH_SEMESTER':
        return 'Periode tengah semester';
      case 'SEMESTER':
        return 'Pilih semester';
      default:
        return 'Label periode';
    }
  }

  void _syncEvaluationPeriodLabel({bool forceReset = false}) {
    final options = _evaluationPeriodLabelOptions(_selectedChoice);
    if (options.isEmpty) {
      if (forceReset) {
        _periodLabelController.clear();
      }
      return;
    }
    final current = _periodLabelController.text.trim();
    final exists = options.any((item) => item['key'] == current);
    if (forceReset || !exists) {
      _periodLabelController.text = options.first['key'] ?? '';
    }
  }

  String? _evaluationAverageScore() {
    final values = _evaluationQuestions
        .map((item) => double.tryParse(item.scoreController.text.trim()))
        .whereType<double>()
        .toList();
    if (values.isEmpty) {
      return null;
    }
    final average = values.reduce((left, right) => left + right) / values.length;
    return average.toStringAsFixed(2);
  }

  List<Widget> _cards(
    List<dynamic> items,
    String Function(Map<String, dynamic>) title,
    String Function(Map<String, dynamic>) subtitle,
    String Function(Map<String, dynamic>) badge,
  ) {
    if (items.isEmpty) {
      return const [
        AppEmptyState(
          title: 'Belum Ada Data',
          subtitle: 'Data untuk bagian ini belum tersedia.',
        ),
      ];
    }
    return items.map((item) {
      final row = JsonHelper.asMap(item);
      final badgeText = badge(row);
      return AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title(row),
                      style: const TextStyle(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 6),
                  Text(
                    subtitle(row),
                    style: const TextStyle(
                        color: AppColors.textSecondary, height: 1.4),
                  ),
                ],
              ),
            ),
            if (badgeText.isNotEmpty) ...[
              const SizedBox(width: 10),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F1FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  badgeText,
                  style: const TextStyle(
                    color: Color(0xFF2563EB),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ],
        ),
      );
    }).toList();
  }

  List<Widget> _academicSummaryCards(List<dynamic> items) {
    if (items.isEmpty) {
      return const [
        AppEmptyState(
          title: 'Belum Ada Ringkasan Nilai',
          subtitle: 'Ringkasan akademik untuk peserta ini belum tersedia.',
        ),
      ];
    }

    String scoreText(Map<String, dynamic> averages, String key) {
      final value = averages[key];
      if (value == null || '$value'.isEmpty) return '-';
      return JsonHelper.asString(value);
    }

    Widget statRow(String label, String value, {bool emphasize = false}) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  color: emphasize ? const Color(0xFF0F172A) : AppColors.textSecondary,
                  fontWeight: emphasize ? FontWeight.w800 : FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              value,
              style: TextStyle(
                color: emphasize ? const Color(0xFF2563EB) : const Color(0xFF0F172A),
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      );
    }

    return items.map((item) {
      final row = JsonHelper.asMap(item);
      final averages = JsonHelper.asMap(row['type_averages']);
      return AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              JsonHelper.asString(row['subject_name']),
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            statRow('Rata-rata Tugas', scoreText(averages, 'TUGAS')),
            statRow('Rata-rata Ulangan Harian', scoreText(averages, 'UH')),
            statRow('Rata-rata UTS', scoreText(averages, 'UTS')),
            statRow('Rata-rata UAS', scoreText(averages, 'UAS')),
            const SizedBox(height: 2),
            statRow(
              'Nilai Akhir (Raport)',
              JsonHelper.asString(row['final_score'], fallback: '-'),
              emphasize: true,
            ),
          ],
        ),
      );
    }).toList();
  }

  List<Widget> _academicHistoryCards(List<dynamic> items) {
    if (items.isEmpty) {
      return const [
        AppEmptyState(
          title: 'Belum Ada Riwayat Akademik',
          subtitle: 'Riwayat nilai akademik untuk peserta ini belum tersedia.',
        ),
      ];
    }

    Widget infoLine(String label, String value) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Text(
          '$label: $value',
          style: const TextStyle(
            color: AppColors.textSecondary,
            height: 1.35,
          ),
        ),
      );
    }

    return items.map((item) {
      final row = JsonHelper.asMap(item);
      final notes = JsonHelper.asString(row['notes']);
      return AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    JsonHelper.asString(row['subject_name']),
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  infoLine('Tipe nilai', JsonHelper.asString(row['type_label'])),
                  infoLine(
                    'Tanggal',
                    AppDateFormatter.shortDate(
                      JsonHelper.asString(row['created_at']),
                    ),
                  ),
                  if (notes.trim().isNotEmpty)
                    infoLine('Catatan', notes),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFE8F1FF),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                JsonHelper.asString(row['score']),
                style: const TextStyle(
                  color: Color(0xFF2563EB),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      );
    }).toList();
  }

  Widget _recapCard(String title, Map<String, dynamic> values) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionTitle(title: title),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: values.entries.map((entry) {
              return Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F1FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  '${entry.key}: ${JsonHelper.asString(entry.value)}',
                  style: const TextStyle(
                    color: Color(0xFF2563EB),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _EvaluationQuestionInput {
  _EvaluationQuestionInput()
      : surahController = TextEditingController(),
        ayatController = TextEditingController(),
        scoreController = TextEditingController();

  final TextEditingController surahController;
  final TextEditingController ayatController;
  final TextEditingController scoreController;

  void dispose() {
    surahController.dispose();
    ayatController.dispose();
    scoreController.dispose();
  }
}

class _PickerOption {
  const _PickerOption({
    required this.value,
    required this.label,
    this.subtitle,
  });

  final String value;
  final String label;
  final String? subtitle;
}

class _Banner extends StatelessWidget {
  const _Banner({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF143A6F), Color(0xFF2F80ED)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Text(
        title,
        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }
}
