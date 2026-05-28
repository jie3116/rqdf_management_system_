import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/currency_formatter.dart';
import '../../../../shared/models/view_state.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/app_empty_state.dart';
import '../../../../shared/widgets/app_error_state.dart';
import '../../../../shared/widgets/app_loading_view.dart';
import '../../../../shared/widgets/section_title.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../auth/presentation/screens/login_screen.dart';
import '../../../auth/presentation/widgets/role_switcher_button.dart';
import '../../data/models/boarding_attendance_model.dart';
import '../../data/models/boarding_dashboard_model.dart';
import '../../data/models/boarding_savings_model.dart';
import '../providers/boarding_dashboard_provider.dart';

class BoardingDashboardScreen extends StatefulWidget {
  const BoardingDashboardScreen({super.key});

  static const String routeName = '/boarding-dashboard';

  @override
  State<BoardingDashboardScreen> createState() =>
      _BoardingDashboardScreenState();
}

class _BoardingDashboardScreenState extends State<BoardingDashboardScreen>
    with WidgetsBindingObserver {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<BoardingDashboardProvider>().fetchDashboard();
      context.read<BoardingDashboardProvider>().fetchAttendance();
      context.read<BoardingDashboardProvider>().fetchSavings();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && mounted) {
      context
          .read<BoardingDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
      context.read<BoardingDashboardProvider>().fetchAttendance();
      context
          .read<BoardingDashboardProvider>()
          .fetchSavings(forceRefresh: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        automaticallyImplyLeading: false,
        backgroundColor: AppColors.background,
        title: const Text(
          'Wali Asrama',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          const RoleSwitcherButton(),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            onPressed: _logout,
          ),
        ],
      ),
      body: IndexedStack(
        index: _selectedIndex,
        children: const [
          _BoardingHomeTab(),
          _BoardingAttendanceTab(),
          _BoardingSavingsTab(),
          _BoardingDormitoryTab(),
          _BoardingProfileTab(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        height: 74,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        indicatorColor: const Color(0xFFE8F1FF),
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) =>
            setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(
            icon: Icon(Icons.fact_check_outlined),
            label: 'Absensi',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            label: 'Tabungan',
          ),
          NavigationDestination(
            icon: Icon(Icons.apartment_outlined),
            label: 'Asrama',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            label: 'Profil',
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    await context.read<AuthProvider>().logout();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil(
      LoginScreen.routeName,
      (_) => false,
    );
  }
}

class _BoardingHomeTab extends StatelessWidget {
  const _BoardingHomeTab();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<BoardingDashboardProvider>();

    return RefreshIndicator(
      onRefresh: () => provider.fetchDashboard(forceRefresh: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          if (provider.dashboardState == ViewState.loading)
            const SizedBox(
              height: 260,
              child: AppLoadingView(message: 'Memuat dashboard asrama...'),
            )
          else if (provider.dashboardState == ViewState.error)
            AppErrorState(
              message: provider.dashboardError ?? 'Terjadi kesalahan.',
              onRetry: () => provider.fetchDashboard(forceRefresh: true),
            )
          else if (provider.dashboard == null)
            const AppEmptyState(
              title: 'Dashboard Belum Tersedia',
              subtitle: 'Data wali asrama belum tersedia.',
            )
          else
            _BoardingHomeContent(dashboard: provider.dashboard!),
        ],
      ),
    );
  }
}

class _BoardingHomeContent extends StatelessWidget {
  const _BoardingHomeContent({required this.dashboard});

  final BoardingDashboardModel dashboard;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _BoardingHeader(profile: dashboard.profile),
        const SizedBox(height: 18),
        _SummaryGrid(summary: dashboard.summary),
        const SizedBox(height: 22),
        SectionTitle(
          title: 'Jadwal Hari Ini',
          trailing: _InfoBadge(label: dashboard.todayName),
        ),
        const SizedBox(height: 10),
        if (dashboard.todaySchedules.isEmpty)
          const AppEmptyState(
            title: 'Tidak Ada Jadwal',
            subtitle: 'Jadwal kegiatan asrama hari ini belum tersedia.',
          )
        else
          ...dashboard.todaySchedules.map((item) => _ScheduleTile(item: item)),
        const SizedBox(height: 22),
        const SectionTitle(title: 'Asrama Saya'),
        const SizedBox(height: 10),
        if (dashboard.dormitories.isEmpty)
          const AppEmptyState(
            title: 'Belum Ada Asrama',
            subtitle: 'Akun ini belum ditugaskan sebagai wali asrama.',
          )
        else
          ...dashboard.dormitories.map((item) => _DormitoryTile(item: item)),
      ],
    );
  }
}

class _BoardingAttendanceTab extends StatefulWidget {
  const _BoardingAttendanceTab();

  @override
  State<_BoardingAttendanceTab> createState() => _BoardingAttendanceTabState();
}

class _BoardingAttendanceTabState extends State<_BoardingAttendanceTab> {
  final Map<int, String> _statusByStudentId = <int, String>{};
  final Map<int, TextEditingController> _noteControllers =
      <int, TextEditingController>{};
  int? _selectedDormitoryId;
  int? _selectedScheduleId;
  String? _selectedDate;
  String? _lastSyncedFormKey;

  @override
  void dispose() {
    for (final controller in _noteControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<BoardingDashboardProvider>();
    final attendance = provider.attendance;

    if (attendance != null) {
      _syncForm(attendance);
    }

    return RefreshIndicator(
      onRefresh: () => _load(provider),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          const SectionTitle(title: 'Input Absensi Asrama'),
          const SizedBox(height: 12),
          if (provider.attendanceState == ViewState.loading)
            const SizedBox(
              height: 260,
              child: AppLoadingView(message: 'Memuat form absensi...'),
            )
          else if (provider.attendanceState == ViewState.error)
            AppErrorState(
              message: provider.attendanceError ?? 'Terjadi kesalahan.',
              onRetry: () => _load(provider),
            )
          else if (attendance == null)
            const AppEmptyState(
              title: 'Form Belum Tersedia',
              subtitle: 'Data absensi asrama belum dimuat.',
            )
          else
            _attendanceForm(context, provider, attendance),
        ],
      ),
    );
  }

  Widget _attendanceForm(
    BuildContext context,
    BoardingDashboardProvider provider,
    BoardingAttendanceModel attendance,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AppCard(
          child: Column(
            children: [
              DropdownButtonFormField<int>(
                initialValue: _selectedDormitoryId,
                decoration: const InputDecoration(labelText: 'Asrama'),
                items: attendance.dormitories
                    .map(
                      (item) => DropdownMenuItem<int>(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedDormitoryId = value;
                    _selectedScheduleId = null;
                  });
                  _load(provider);
                },
              ),
              const SizedBox(height: 10),
              TextFormField(
                initialValue: _selectedDate ?? attendance.date,
                decoration: const InputDecoration(
                  labelText: 'Tanggal',
                  hintText: 'YYYY-MM-DD',
                ),
                keyboardType: TextInputType.datetime,
                onChanged: (value) => _selectedDate = value.trim(),
                onFieldSubmitted: (_) => _load(provider),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<int>(
                initialValue: attendance.schedules
                        .any((item) => item.id == _selectedScheduleId)
                    ? _selectedScheduleId
                    : null,
                decoration: const InputDecoration(labelText: 'Jadwal'),
                items: attendance.schedules
                    .map(
                      (item) => DropdownMenuItem<int>(
                        value: item.id,
                        child: Text('${item.startTime} ${item.activityName}'),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  setState(() => _selectedScheduleId = value);
                  _load(provider);
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _InfoCard(
          title: '${attendance.dayName}, ${attendance.date}',
          subtitle:
              '${attendance.students.length} santri dalam daftar absensi.',
          icon: Icons.today_outlined,
        ),
        const SizedBox(height: 16),
        if (attendance.schedules.isEmpty)
          const AppEmptyState(
            title: 'Tidak Ada Jadwal',
            subtitle: 'Tidak ada jadwal kegiatan untuk asrama dan tanggal ini.',
          )
        else if (attendance.students.isEmpty)
          const AppEmptyState(
            title: 'Tidak Ada Santri',
            subtitle: 'Belum ada santri pada asrama yang dipilih.',
          )
        else ...[
          ...attendance.students.map(
            (student) => _StudentAttendanceTile(
              student: student,
              options: attendance.statusOptions,
              selectedStatus: _statusByStudentId[student.id] ?? 'HADIR',
              noteController: _noteControllers[student.id]!,
              onStatusChanged: (value) {
                if (value == null) return;
                setState(() => _statusByStudentId[student.id] = value);
              },
            ),
          ),
          const SizedBox(height: 10),
          AppButton(
            label:
                provider.isSavingAttendance ? 'Menyimpan...' : 'Simpan Absensi',
            icon: Icons.save_outlined,
            loading: provider.isSavingAttendance,
            onPressed: () => _save(provider, attendance),
          ),
        ],
      ],
    );
  }

  void _syncForm(BoardingAttendanceModel attendance) {
    final formKey =
        '${attendance.date}:${attendance.selectedDormitoryId}:${attendance.selectedScheduleId}';
    if (_lastSyncedFormKey != formKey) {
      _lastSyncedFormKey = formKey;
      _statusByStudentId.clear();
      for (final controller in _noteControllers.values) {
        controller.dispose();
      }
      _noteControllers.clear();
      _selectedDate = attendance.date;
    }

    _selectedDormitoryId = _selectedDormitoryId != null &&
            attendance.dormitories
                .any((item) => item.id == _selectedDormitoryId)
        ? _selectedDormitoryId
        : (attendance.selectedDormitoryId > 0
            ? attendance.selectedDormitoryId
            : null);
    _selectedScheduleId = _selectedScheduleId != null &&
            attendance.schedules.any((item) => item.id == _selectedScheduleId)
        ? _selectedScheduleId
        : (attendance.selectedScheduleId > 0
            ? attendance.selectedScheduleId
            : null);
    _selectedDate ??= attendance.date;

    for (final student in attendance.students) {
      _statusByStudentId.putIfAbsent(
        student.id,
        () => student.status.isNotEmpty ? student.status : 'HADIR',
      );
      _noteControllers.putIfAbsent(
        student.id,
        () => TextEditingController(text: student.notes),
      );
    }
  }

  Future<void> _load(BoardingDashboardProvider provider) {
    return provider.fetchAttendance(
      dormitoryId: _selectedDormitoryId,
      scheduleId: _selectedScheduleId,
      date: _selectedDate,
    );
  }

  Future<void> _save(
    BoardingDashboardProvider provider,
    BoardingAttendanceModel attendance,
  ) async {
    final dormitoryId = _selectedDormitoryId ?? attendance.selectedDormitoryId;
    final scheduleId = _selectedScheduleId ?? attendance.selectedScheduleId;
    final date = (_selectedDate ?? attendance.date).trim();
    if (dormitoryId <= 0 || scheduleId <= 0 || date.isEmpty) {
      _showSnack('Asrama, tanggal, dan jadwal wajib dipilih.');
      return;
    }

    final records = attendance.students
        .map(
          (student) => BoardingAttendanceRecordInput(
            studentId: student.id,
            status: _statusByStudentId[student.id] ?? 'HADIR',
            notes: _noteControllers[student.id]?.text.trim(),
          ),
        )
        .toList();
    final error = await provider.saveAttendance(
      dormitoryId: dormitoryId,
      scheduleId: scheduleId,
      date: date,
      records: records,
    );
    if (!mounted) return;
    if (error != null) {
      _showSnack(error);
      return;
    }
    _showSnack('Absensi asrama berhasil disimpan.');
    await provider.fetchDashboard(forceRefresh: true);
    await _load(provider);
  }

  void _showSnack(String message) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }
}

class _BoardingSavingsTab extends StatefulWidget {
  const _BoardingSavingsTab();

  @override
  State<_BoardingSavingsTab> createState() => _BoardingSavingsTabState();
}

class _BoardingSavingsTabState extends State<_BoardingSavingsTab> {
  final TextEditingController _oldOfficerPinController =
      TextEditingController();
  final TextEditingController _officerPinController = TextEditingController();
  final TextEditingController _officerPinConfirmController =
      TextEditingController();
  final TextEditingController _withdrawAmountController =
      TextEditingController();
  final TextEditingController _withdrawStudentPinController =
      TextEditingController();
  final TextEditingController _withdrawOfficerPinController =
      TextEditingController();
  int? _selectedStudentId;

  @override
  void dispose() {
    _oldOfficerPinController.dispose();
    _officerPinController.dispose();
    _officerPinConfirmController.dispose();
    _withdrawAmountController.dispose();
    _withdrawStudentPinController.dispose();
    _withdrawOfficerPinController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<BoardingDashboardProvider>();
    final savings = provider.savings;
    if (savings != null &&
        _selectedStudentId == null &&
        savings.students.isNotEmpty) {
      _selectedStudentId = savings.students.first.id;
    }

    return RefreshIndicator(
      onRefresh: () => provider.fetchSavings(forceRefresh: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          const SectionTitle(title: 'Tabungan Santri'),
          const SizedBox(height: 12),
          if (provider.savingsState == ViewState.loading)
            const SizedBox(
              height: 260,
              child: AppLoadingView(message: 'Memuat tabungan santri...'),
            )
          else if (provider.savingsState == ViewState.error)
            AppErrorState(
              message: provider.savingsError ?? 'Terjadi kesalahan.',
              onRetry: () => provider.fetchSavings(forceRefresh: true),
            )
          else if (savings == null)
            const AppEmptyState(
              title: 'Data Belum Tersedia',
              subtitle: 'Data tabungan santri belum dimuat.',
            )
          else
            _savingsContent(context, provider, savings),
        ],
      ),
    );
  }

  Widget _savingsContent(
    BuildContext context,
    BoardingDashboardProvider provider,
    BoardingSavingsModel savings,
  ) {
    final selectedStudent = savings.students
        .where((student) => student.id == _selectedStudentId)
        .firstOrNull;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SavingsSummaryCard(savings: savings),
        const SizedBox(height: 14),
        if (savings.officerPinLockedMinutes > 0)
          _InfoCard(
            title: 'PIN petugas terkunci',
            subtitle:
                'Coba lagi ${savings.officerPinLockedMinutes} menit lagi.',
            icon: Icons.lock_clock_outlined,
          ),
        if (savings.officerPinLockedMinutes > 0) const SizedBox(height: 14),
        _OfficerPinCard(
          oldPinController: _oldOfficerPinController,
          pinController: _officerPinController,
          pinConfirmController: _officerPinConfirmController,
          officerPinExists: savings.officerPinExists,
          loading: provider.isSavingOfficerPin,
          onSubmit: () => _setOfficerPin(provider),
        ),
        const SizedBox(height: 14),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Penarikan Tunai',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 12),
              if (savings.students.isEmpty)
                const AppEmptyState(
                  title: 'Belum Ada Santri',
                  subtitle: 'Belum ada akun tabungan santri pesantren.',
                )
              else ...[
                DropdownButtonFormField<int>(
                  isExpanded: true,
                  initialValue: selectedStudent?.id,
                  decoration: const InputDecoration(labelText: 'Santri'),
                  selectedItemBuilder: (context) {
                    return savings.students.map((student) {
                      return Align(
                        alignment: Alignment.centerLeft,
                        child: Text(
                          '${student.name} (${CurrencyFormatter.rupiah(student.balance)})',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      );
                    }).toList();
                  },
                  items: savings.students
                      .map(
                        (student) => DropdownMenuItem<int>(
                          value: student.id,
                          child: Text(
                            '${student.name} (${CurrencyFormatter.rupiah(student.balance)})',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (value) =>
                      setState(() => _selectedStudentId = value),
                ),
                const SizedBox(height: 10),
                if (selectedStudent != null)
                  _InfoCard(
                    title:
                        'Saldo ${CurrencyFormatter.rupiah(selectedStudent.balance)}',
                    subtitle: selectedStudent.hasPin
                        ? 'PIN santri sudah tersedia.'
                        : 'PIN santri belum diset oleh wali/santri.',
                    icon: Icons.account_balance_wallet_outlined,
                  ),
                const SizedBox(height: 10),
                TextField(
                  controller: _withdrawAmountController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Nominal penarikan',
                    hintText: 'Contoh: 50000',
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _QuickAmountChip(
                      label: '10rb',
                      amount: 10000,
                      onSelected: _setWithdrawAmount,
                    ),
                    _QuickAmountChip(
                      label: '20rb',
                      amount: 20000,
                      onSelected: _setWithdrawAmount,
                    ),
                    _QuickAmountChip(
                      label: '50rb',
                      amount: 50000,
                      onSelected: _setWithdrawAmount,
                    ),
                    _QuickAmountChip(
                      label: '100rb',
                      amount: 100000,
                      onSelected: _setWithdrawAmount,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _withdrawStudentPinController,
                  keyboardType: TextInputType.number,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'PIN santri'),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _withdrawOfficerPinController,
                  keyboardType: TextInputType.number,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: 'PIN petugas'),
                ),
                const SizedBox(height: 12),
                AppButton(
                  label: provider.isWithdrawingSavings
                      ? 'Memproses...'
                      : 'Catat Penarikan',
                  icon: Icons.payments_outlined,
                  loading: provider.isWithdrawingSavings,
                  onPressed: () => _withdraw(provider, selectedStudent),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 18),
        const SectionTitle(title: 'Saldo Santri'),
        const SizedBox(height: 10),
        if (savings.students.isEmpty)
          const AppEmptyState(
            title: 'Belum Ada Data',
            subtitle: 'Daftar tabungan santri masih kosong.',
          )
        else
          ...savings.students
              .map((student) => _SavingsStudentTile(student: student)),
      ],
    );
  }

  Future<void> _setOfficerPin(BoardingDashboardProvider provider) async {
    final pin = _officerPinController.text.trim();
    final pinConfirm = _officerPinConfirmController.text.trim();
    if (pin.length < 4 || int.tryParse(pin) == null) {
      _showSnack('PIN petugas harus angka minimal 4 digit.');
      return;
    }
    if (pin != pinConfirm) {
      _showSnack('Konfirmasi PIN petugas tidak sama.');
      return;
    }
    final error = await provider.setOfficerPin(
      oldPin: _oldOfficerPinController.text.trim(),
      pin: pin,
      pinConfirm: pinConfirm,
    );
    if (!mounted) return;
    if (error != null) {
      _showSnack(error);
      return;
    }
    _oldOfficerPinController.clear();
    _officerPinController.clear();
    _officerPinConfirmController.clear();
    _showSnack('PIN petugas berhasil disimpan.');
    await provider.fetchSavings(forceRefresh: true);
  }

  Future<void> _withdraw(
    BoardingDashboardProvider provider,
    BoardingSavingsStudentModel? selectedStudent,
  ) async {
    if (selectedStudent == null) {
      _showSnack('Pilih santri terlebih dahulu.');
      return;
    }
    final amount = int.tryParse(
          _withdrawAmountController.text
              .trim()
              .replaceAll('.', '')
              .replaceAll(',', ''),
        ) ??
        0;
    if (amount <= 0) {
      _showSnack('Nominal penarikan harus lebih besar dari 0.');
      return;
    }
    if (amount > selectedStudent.balance) {
      _showSnack('Saldo santri tidak mencukupi.');
      return;
    }
    final studentPin = _withdrawStudentPinController.text.trim();
    final officerPin = _withdrawOfficerPinController.text.trim();
    if (studentPin.isEmpty || officerPin.isEmpty) {
      _showSnack('PIN santri dan PIN petugas wajib diisi.');
      return;
    }

    final error = await provider.withdrawSavings(
      studentId: selectedStudent.id,
      amount: amount,
      studentPin: studentPin,
      officerPin: officerPin,
    );
    if (!mounted) return;
    if (error != null) {
      _showSnack(error);
      return;
    }
    _withdrawAmountController.clear();
    _withdrawStudentPinController.clear();
    _withdrawOfficerPinController.clear();
    _showSnack('Penarikan tunai berhasil dicatat.');
    await provider.fetchSavings(forceRefresh: true);
  }

  void _setWithdrawAmount(int amount) {
    _withdrawAmountController.text = '$amount';
  }

  void _showSnack(String message) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }
}

class _BoardingDormitoryTab extends StatelessWidget {
  const _BoardingDormitoryTab();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<BoardingDashboardProvider>();
    final dashboard = provider.dashboard;
    if (provider.dashboardState == ViewState.loading) {
      return const AppLoadingView(message: 'Memuat asrama...');
    }
    if (provider.dashboardState == ViewState.error) {
      return AppErrorState(
        message: provider.dashboardError ?? 'Terjadi kesalahan.',
        onRetry: () => provider.fetchDashboard(forceRefresh: true),
      );
    }
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
      children: [
        const SectionTitle(title: 'Asrama Saya'),
        const SizedBox(height: 12),
        if (dashboard == null || dashboard.dormitories.isEmpty)
          const AppEmptyState(
            title: 'Belum Ada Asrama',
            subtitle: 'Akun ini belum ditugaskan sebagai wali asrama.',
          )
        else
          ...dashboard.dormitories.map((item) => _DormitoryTile(item: item)),
      ],
    );
  }
}

class _BoardingProfileTab extends StatelessWidget {
  const _BoardingProfileTab();

  @override
  Widget build(BuildContext context) {
    final dashboard = context.watch<BoardingDashboardProvider>().dashboard;
    final profile = dashboard?.profile;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
      children: [
        const SectionTitle(title: 'Profil Wali Asrama'),
        const SizedBox(height: 12),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                profile?.name ?? '-',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                profile?.phone ?? '-',
                style: const TextStyle(color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _BoardingHeader extends StatelessWidget {
  const _BoardingHeader({required this.profile});

  final BoardingGuardianProfile profile;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(Icons.apartment_outlined, color: Colors.white),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  profile.name,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Dashboard pengasuhan asrama',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.82),
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

class _SummaryGrid extends StatelessWidget {
  const _SummaryGrid({required this.summary});

  final BoardingSummary summary;

  @override
  Widget build(BuildContext context) {
    final items = [
      MapEntry('Asrama', '${summary.dormitoryCount}'),
      MapEntry('Santri', '${summary.studentCount}'),
      MapEntry('Absensi hari ini', '${summary.attendanceToday}'),
      MapEntry('Jadwal hari ini', '${summary.scheduleToday}'),
    ];
    return GridView.builder(
      itemCount: items.length,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
        mainAxisExtent: 82,
      ),
      itemBuilder: (_, index) {
        final item = items[index];
        return AppCard(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                item.key,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                item.value,
                style: const TextStyle(
                  color: AppColors.primary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _DormitoryTile extends StatelessWidget {
  const _DormitoryTile({required this.item});

  final BoardingDormitoryModel item;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.accentBlueSoft,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.bed_outlined, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.name,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  '${item.studentCount} santri • ${item.genderLabel}',
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          _InfoBadge(label: item.capacity > 0 ? 'Kap. ${item.capacity}' : '-'),
        ],
      ),
    );
  }
}

class _ScheduleTile extends StatelessWidget {
  const _ScheduleTile({required this.item});

  final BoardingScheduleModel item;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          _TimeBadge(start: item.startTime, end: item.endTime),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.activityName,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  item.dormitoryName,
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

class _StudentAttendanceTile extends StatelessWidget {
  const _StudentAttendanceTile({
    required this.student,
    required this.options,
    required this.selectedStatus,
    required this.noteController,
    required this.onStatusChanged,
  });

  final BoardingStudentAttendanceModel student;
  final List<BoardingStatusOption> options;
  final String selectedStatus;
  final TextEditingController noteController;
  final ValueChanged<String?> onStatusChanged;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      student.name,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'NIS ${student.nis}',
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              SizedBox(
                width: 118,
                child: DropdownButtonFormField<String>(
                  initialValue:
                      options.any((item) => item.key == selectedStatus)
                          ? selectedStatus
                          : 'HADIR',
                  items: options
                      .map(
                        (item) => DropdownMenuItem<String>(
                          value: item.key,
                          child: Text(item.label),
                        ),
                      )
                      .toList(),
                  onChanged: onStatusChanged,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: noteController,
            maxLines: 1,
            decoration: const InputDecoration(
              labelText: 'Catatan',
              hintText: 'Opsional',
            ),
          ),
        ],
      ),
    );
  }
}

class _SavingsSummaryCard extends StatelessWidget {
  const _SavingsSummaryCard({required this.savings});

  final BoardingSavingsModel savings;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Ringkasan Tabungan',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _MiniMetric(
                  label: 'Santri',
                  value: '${savings.summary.studentCount}',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MiniMetric(
                  label: 'Total saldo',
                  value: CurrencyFormatter.rupiah(savings.summary.totalBalance),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _InfoBadge(
            label: savings.officerPinExists
                ? 'PIN petugas aktif'
                : 'PIN petugas belum diset',
          ),
        ],
      ),
    );
  }
}

class _OfficerPinCard extends StatelessWidget {
  const _OfficerPinCard({
    required this.oldPinController,
    required this.pinController,
    required this.pinConfirmController,
    required this.officerPinExists,
    required this.loading,
    required this.onSubmit,
  });

  final TextEditingController oldPinController;
  final TextEditingController pinController;
  final TextEditingController pinConfirmController;
  final bool officerPinExists;
  final bool loading;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'PIN Petugas',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          if (officerPinExists) ...[
            TextField(
              controller: oldPinController,
              keyboardType: TextInputType.number,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'PIN lama'),
            ),
            const SizedBox(height: 10),
          ],
          TextField(
            controller: pinController,
            keyboardType: TextInputType.number,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'PIN petugas baru',
              hintText: 'Minimal 4 digit',
            ),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: pinConfirmController,
            keyboardType: TextInputType.number,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Konfirmasi PIN'),
          ),
          const SizedBox(height: 12),
          AppButton(
            label: loading ? 'Menyimpan...' : 'Simpan PIN Petugas',
            icon: Icons.lock_outline,
            loading: loading,
            onPressed: onSubmit,
          ),
        ],
      ),
    );
  }
}

class _SavingsStudentTile extends StatelessWidget {
  const _SavingsStudentTile({required this.student});

  final BoardingSavingsStudentModel student;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.accentBlueSoft,
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.account_balance_wallet_outlined,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  student.name,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  '${student.dormitoryName} • NIS ${student.nis}',
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                CurrencyFormatter.rupiah(student.balance),
                style: const TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                student.hasPin ? 'PIN OK' : 'PIN kosong',
                style: TextStyle(
                  color: student.hasPin ? AppColors.success : AppColors.warning,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickAmountChip extends StatelessWidget {
  const _QuickAmountChip({
    required this.label,
    required this.amount,
    required this.onSelected,
  });

  final String label;
  final int amount;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      label: Text(label),
      onPressed: () => onSelected(amount),
    );
  }
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FBFF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderSoft),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Row(
        children: [
          Icon(icon, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(
                  subtitle,
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

extension _IterableExt<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

class _TimeBadge extends StatelessWidget {
  const _TimeBadge({required this.start, required this.end});

  final String start;
  final String end;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 70,
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Text(
            start,
            style: const TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            end,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoBadge extends StatelessWidget {
  const _InfoBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.accentBlueSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.primary,
          fontWeight: FontWeight.w800,
          fontSize: 12,
        ),
      ),
    );
  }
}
