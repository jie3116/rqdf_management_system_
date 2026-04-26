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

class TeacherAttendanceInputArgs {
  TeacherAttendanceInputArgs({
    required this.classId,
    required this.title,
  });

  final int classId;
  final String title;
}

class TeacherAttendanceInputScreen extends StatefulWidget {
  const TeacherAttendanceInputScreen({super.key, required this.args});

  static const routeName = '/teacher-attendance-input';
  final TeacherAttendanceInputArgs args;

  @override
  State<TeacherAttendanceInputScreen> createState() =>
      _TeacherAttendanceInputScreenState();
}

class _TeacherAttendanceInputScreenState
    extends State<TeacherAttendanceInputScreen> {
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  String _selectedDate = DateTime.now().toIso8601String().split('T').first;
  int? _selectedClassId;
  Map<String, dynamic>? _payload;
  final Map<String, String> _statusSelections = {};
  final Map<String, TextEditingController> _noteControllers = {};

  @override
  void initState() {
    super.initState();
    _selectedClassId = widget.args.classId;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    for (final controller in _noteControllers.values) {
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
        key: 'input-attendance',
        query: {'class_id': _selectedClassId, 'date': _selectedDate},
      );
      final existing = JsonHelper.asMap(payload['existing_attendance']);
      final statuses = JsonHelper.asList(payload['attendance_statuses']);
      final defaultStatus = _defaultAttendanceStatus(statuses);
      final activeKeys = <String>{};
      for (final item in JsonHelper.asList(payload['participants'])) {
        final row = JsonHelper.asMap(item);
        final key = JsonHelper.asString(row['key']);
        activeKeys.add(key);
        final existingStatus =
            JsonHelper.asString(JsonHelper.asMap(existing[key])['status']);
        _statusSelections[key] = existingStatus.isNotEmpty
            ? existingStatus
            : (_statusSelections[key]?.trim().isNotEmpty == true
                ? _statusSelections[key]!
                : defaultStatus);
        _noteControllers.putIfAbsent(key, TextEditingController.new).text =
            JsonHelper.asString(JsonHelper.asMap(existing[key])['notes']);
      }
      final removedKeys = _noteControllers.keys
          .where((key) => !activeKeys.contains(key))
          .toList();
      for (final key in removedKeys) {
        _noteControllers.remove(key)?.dispose();
        _statusSelections.remove(key);
      }
      _selectedClassId ??= JsonHelper.asInt(
        JsonHelper.asMap(payload['selected_class'])['id'],
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
        _error = 'Gagal memuat form absensi.';
        _loading = false;
      });
    }
  }

  String _defaultAttendanceStatus(List<dynamic> statuses) {
    for (final item in statuses) {
      final row = JsonHelper.asMap(item);
      final key = JsonHelper.asString(row['key']);
      final label = JsonHelper.asString(row['label']).toLowerCase();
      if (key.toUpperCase() == 'HADIR' ||
          key.toUpperCase() == 'PRESENT' ||
          label == 'hadir') {
        return key;
      }
    }
    if (statuses.isEmpty) {
      return '';
    }
    return JsonHelper.asString(JsonHelper.asMap(statuses.first)['key']);
  }

  Future<void> _submit() async {
    setState(() => _submitting = true);
    try {
      await context.read<TeacherActionRepository>().submit(
        key: 'input-attendance',
        body: {
          'class_id': _selectedClassId,
          'attendance_date': _selectedDate,
          'records': _statusSelections.entries
              .where((entry) => entry.value.trim().isNotEmpty)
              .map((entry) => {
                    'participant_key': entry.key,
                    'status': entry.value,
                    'notes': _noteControllers[entry.key]?.text.trim() ?? '',
                  })
              .toList(),
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Absensi berhasil disimpan.')),
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
      appBar: AppBar(title: const Text('Input Absensi')),
      body: _loading
          ? const AppLoadingView(message: 'Memuat form absensi...')
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
                      TextField(
                        controller: TextEditingController(text: _selectedDate)
                          ..selection = TextSelection.collapsed(
                              offset: _selectedDate.length),
                        decoration: const InputDecoration(
                          labelText: 'Tanggal absensi (YYYY-MM-DD)',
                        ),
                        onChanged: (value) => _selectedDate = value.trim(),
                      ),
                      const SizedBox(height: 18),
                      const SectionTitle(title: 'Daftar Kehadiran'),
                      const SizedBox(height: 10),
                      ..._participantCards(),
                      const SizedBox(height: 12),
                      AppButton(
                        label: 'Simpan Absensi',
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
            child: const Icon(
              Icons.fact_check_outlined,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Input Absensi',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18),
                ),
                SizedBox(height: 4),
                Text(
                  'Pilih kelas, tentukan tanggal, lalu catat kehadiran setiap peserta.',
                  style: TextStyle(
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
        });
        _load();
      },
      decoration: const InputDecoration(labelText: 'Pilih kelas'),
    );
  }

  List<Widget> _participantCards() {
    final payload = _payload ?? const <String, dynamic>{};
    final participants = JsonHelper.asList(payload['participants']);
    final statuses = JsonHelper.asList(payload['attendance_statuses']);
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
            DropdownButtonFormField<String>(
              initialValue: (_statusSelections[key] ?? '').isEmpty
                  ? null
                  : _statusSelections[key],
              items: statuses.map((item) {
                final status = JsonHelper.asMap(item);
                return DropdownMenuItem<String>(
                  value: JsonHelper.asString(status['key']),
                  child: Text(JsonHelper.asString(status['label'])),
                );
              }).toList(),
              onChanged: (value) =>
                  setState(() => _statusSelections[key] = value ?? ''),
              decoration: const InputDecoration(labelText: 'Status'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _noteControllers[key],
              decoration: const InputDecoration(labelText: 'Catatan'),
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
        key: 'attendance-history',
        title: 'Histori Absensi',
        classId: _selectedClassId,
        participantKey: participantKey,
      ),
    );
  }
}
