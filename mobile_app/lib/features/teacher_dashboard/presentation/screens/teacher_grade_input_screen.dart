import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/json_helper.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/app_empty_state.dart';
import '../../../../shared/widgets/app_error_state.dart';
import '../../../../shared/widgets/app_loading_view.dart';
import '../../../../shared/widgets/section_title.dart';
import '../../data/repositories/teacher_action_repository.dart';
import 'teacher_module_screen.dart';

class TeacherGradeInputArgs {
  TeacherGradeInputArgs({
    required this.classId,
    this.subjectId,
    this.majlisSubjectId,
    required this.title,
  });

  final int classId;
  final int? subjectId;
  final int? majlisSubjectId;
  final String title;
}

class TeacherGradeInputScreen extends StatefulWidget {
  const TeacherGradeInputScreen({super.key, required this.args});

  static const routeName = '/teacher-grade-input';
  final TeacherGradeInputArgs args;

  @override
  State<TeacherGradeInputScreen> createState() =>
      _TeacherGradeInputScreenState();
}

class _TeacherGradeInputScreenState extends State<TeacherGradeInputScreen> {
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  Map<String, dynamic>? _payload;
  String? _selectedGradeType;
  int? _selectedClassId;
  final _notesController = TextEditingController();
  final Map<String, TextEditingController> _scoreControllers = {};

  @override
  void initState() {
    super.initState();
    _selectedClassId = widget.args.classId;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _notesController.dispose();
    for (final controller in _scoreControllers.values) {
      controller.dispose();
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
        key: 'input-grades',
        query: {
          'class_id': _selectedClassId,
          if (widget.args.subjectId != null)
            'subject_id': widget.args.subjectId,
          if (widget.args.majlisSubjectId != null)
            'majlis_subject_id': widget.args.majlisSubjectId,
        },
      );
      _syncScoreControllers(JsonHelper.asList(payload['participants']));
      _selectedClassId ??= JsonHelper.asInt(
        JsonHelper.asMap(payload['selected_class'])['id'],
      );
      _selectedGradeType ??= JsonHelper.asString(
        JsonHelper.asMap(
            JsonHelper.asList(payload['grade_types']).firstOrNull)['key'],
      );
      setState(() {
        _payload = payload;
        _loading = false;
      });
    } on ApiException catch (error) {
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _error = 'Gagal memuat form nilai.';
        _loading = false;
      });
    }
  }

  void _syncScoreControllers(List<dynamic> participants) {
    final activeKeys = <String>{};
    for (final item in participants) {
        final row = JsonHelper.asMap(item);
        final key = JsonHelper.asString(row['key']);
        activeKeys.add(key);
        _scoreControllers.putIfAbsent(key, TextEditingController.new);
      }
    final removedKeys = _scoreControllers.keys
        .where((key) => !activeKeys.contains(key))
        .toList();
    for (final key in removedKeys) {
      _scoreControllers.remove(key)?.dispose();
    }
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    try {
      await context.read<TeacherActionRepository>().submit(
        key: 'input-grades',
        body: {
          'class_id': _selectedClassId,
          'subject_id': widget.args.subjectId,
          'majlis_subject_id': widget.args.majlisSubjectId,
          'grade_type': _selectedGradeType,
          'notes': _notesController.text.trim(),
          'scores': _scoreControllers.entries
              .where((entry) => entry.value.text.trim().isNotEmpty)
              .map((entry) => {
                    'participant_key': entry.key,
                    'score': entry.value.text.trim(),
                  })
              .toList(),
        },
      );
      if (!mounted) return;
      for (final controller in _scoreControllers.values) {
        controller.clear();
      }
      _notesController.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Nilai berhasil disimpan.')),
      );
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Input Nilai')),
      body: _loading
          ? const AppLoadingView(message: 'Memuat form nilai...')
          : _error != null
              ? AppErrorState(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(20),
                    children: [
                      _header(),
                      const SizedBox(height: 18),
                      _classDropdown(),
                      const SizedBox(height: 12),
                      _gradeTypeDropdown(),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _notesController,
                        decoration: const InputDecoration(labelText: 'Catatan'),
                      ),
                      const SizedBox(height: 18),
                      const SectionTitle(title: 'Input Nilai Peserta'),
                      const SizedBox(height: 10),
                      ..._participantCards(),
                      const SizedBox(height: 12),
                      AppButton(
                        label: 'Simpan Nilai',
                        onPressed: _submitting ? null : _submit,
                        loading: _submitting,
                        icon: Icons.save_outlined,
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _header() {
    final payload = _payload ?? const <String, dynamic>{};
    final subject = JsonHelper.asMap(payload['subject']);
    final majlisSubject = JsonHelper.asMap(payload['majlis_subject']);
    final subjectName = JsonHelper.asString(
      subject['name'] ?? majlisSubject['name'],
      fallback: '-',
    );

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Input Nilai',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
          ),
          const SizedBox(height: 6),
          Text(
            subjectName,
            style: const TextStyle(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _classDropdown() {
    final classes =
        JsonHelper.asList((_payload ?? const <String, dynamic>{})['classes']);
    return DropdownButtonFormField<int>(
      initialValue: _selectedClassId != null && _selectedClassId! > 0
          ? _selectedClassId
          : null,
      items: classes.map((item) {
        final row = JsonHelper.asMap(item);
        return DropdownMenuItem<int>(
          value: JsonHelper.asInt(row['id']),
          child: Text(JsonHelper.asString(row['name'])),
        );
      }).toList(),
      onChanged: (value) {
        if (value == null || value == _selectedClassId) return;
        setState(() {
          _selectedClassId = value;
          _payload = null;
          _notesController.clear();
          for (final controller in _scoreControllers.values) {
            controller.clear();
          }
        });
        _load();
      },
      decoration: const InputDecoration(labelText: 'Pilih kelas'),
    );
  }

  Widget _gradeTypeDropdown() {
    final gradeTypes = JsonHelper.asList(
      (_payload ?? const <String, dynamic>{})['grade_types'],
    ).where((item) {
      final row = JsonHelper.asMap(item);
      return JsonHelper.asString(row['key']).toUpperCase() != 'SIKAP';
    }).toList();

    if (_selectedGradeType == 'SIKAP') {
      _selectedGradeType = JsonHelper.asString(
        JsonHelper.asMap(gradeTypes.firstOrNull)['key'],
      );
    }

    return DropdownButtonFormField<String>(
      initialValue:
          (_selectedGradeType ?? '').isEmpty ? null : _selectedGradeType,
      items: gradeTypes.map((item) {
        final row = JsonHelper.asMap(item);
        return DropdownMenuItem<String>(
          value: JsonHelper.asString(row['key']),
          child: Text(JsonHelper.asString(row['label'])),
        );
      }).toList(),
      onChanged: (value) => setState(() => _selectedGradeType = value),
      decoration: const InputDecoration(labelText: 'Tipe nilai'),
    );
  }

  List<Widget> _participantCards() {
    final payload = _payload ?? const <String, dynamic>{};
    final participants = JsonHelper.asList(payload['participants']);
    if (participants.isEmpty) {
      return const [
        AppEmptyState(
          title: 'Belum Ada Peserta',
          subtitle: 'Peserta untuk kelas ini belum tersedia.',
        ),
      ];
    }

    return participants.map((item) {
      final row = JsonHelper.asMap(item);
      final key = JsonHelper.asString(row['key']);
      return AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => _openParticipantHistory(
                participantKey: key,
              ),
              borderRadius: BorderRadius.circular(10),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        JsonHelper.asString(row['display_name']),
                        style: const TextStyle(
                          fontWeight: FontWeight.w800,
                          color: Color(0xFF2563EB),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Icon(
                      Icons.history_rounded,
                      size: 18,
                      color: Color(0xFF2563EB),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '${JsonHelper.asString(row['identifier_label'])}: ${JsonHelper.asString(row['identifier'])}',
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _scoreControllers[key],
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Skor'),
            ),
          ],
        ),
      );
    }).toList();
  }

  void _openParticipantHistory({required String participantKey}) {
    Navigator.of(context).pushNamed(
      TeacherModuleScreen.routeName,
      arguments: TeacherModuleArgs(
        key: 'grade-history',
        title: 'Histori Nilai',
        classId: _selectedClassId,
        participantKey: participantKey,
      ),
    );
  }
}

extension _FirstOrNull on List<dynamic> {
  dynamic get firstOrNull => isEmpty ? null : first;
}
