import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/utils/app_date_formatter.dart';
import '../../../../shared/models/view_state.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/app_empty_state.dart';
import '../../../../shared/widgets/app_error_state.dart';
import '../../../../shared/widgets/app_loading_view.dart';
import '../../../../shared/widgets/section_title.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../auth/presentation/screens/login_screen.dart';
import '../../../parent_dashboard/presentation/widgets/announcements_section.dart';
import '../../data/models/teacher_dashboard_model.dart';
import 'teacher_attendance_input_screen.dart';
import 'teacher_grade_input_screen.dart';
import 'teacher_module_screen.dart';
import '../providers/teacher_dashboard_provider.dart';

class TeacherDashboardScreen extends StatefulWidget {
  const TeacherDashboardScreen({super.key});

  static const String routeName = '/teacher-dashboard';

  @override
  State<TeacherDashboardScreen> createState() => _TeacherDashboardScreenState();
}

class _TeacherDashboardScreenState extends State<TeacherDashboardScreen>
    with WidgetsBindingObserver {
  int _selectedIndex = 0;
  TeacherDashboardProvider? _dashboardProvider;
  int _lastAnnouncementSignal = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TeacherDashboardProvider>().fetchDashboard();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final provider = context.read<TeacherDashboardProvider>();
    if (!identical(_dashboardProvider, provider)) {
      _dashboardProvider?.removeListener(_onDashboardProviderChanged);
      _dashboardProvider = provider;
      _lastAnnouncementSignal = provider.announcementSignal;
      provider.addListener(_onDashboardProviderChanged);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _dashboardProvider?.removeListener(_onDashboardProviderChanged);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && mounted) {
      context
          .read<TeacherDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
    }
  }

  void _onDashboardProviderChanged() {
    if (!mounted) return;
    final provider = _dashboardProvider;
    if (provider == null) return;
    if (provider.announcementSignal == _lastAnnouncementSignal) return;

    _lastAnnouncementSignal = provider.announcementSignal;
    final delta = provider.lastAnnouncementDelta;
    if (delta <= 0) return;

    final label =
        delta == 1 ? 'Ada 1 pengumuman baru.' : 'Ada $delta pengumuman baru.';
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: Text(label),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F7FC),
      appBar: AppBar(
        automaticallyImplyLeading: false,
        backgroundColor: const Color(0xFFF3F7FC),
        title: const Text(
          'RQDF Mobile',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            onPressed: _logout,
          ),
        ],
      ),
      body: IndexedStack(
        index: _selectedIndex,
        children: [
          _TeacherHomeTab(
            onOpenTab: _openTab,
            onOpenGradeInput: _openGradeInput,
            onOpenAttendanceInput: _openAttendanceInput,
            onOpenModule: _openModule,
          ),
          _TeacherInputTab(
            onOpenTab: _openTab,
            onOpenGradeInput: _openGradeInput,
            onOpenAttendanceInput: _openAttendanceInput,
            onOpenModule: _openModule,
          ),
          _TeacherHistoryTab(onOpenTab: _openTab, onOpenModule: _openModule),
          _TeacherHomeroomTab(onOpenTab: _openTab, onOpenModule: _openModule),
          const _TeacherProfileTab(),
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
            icon: Icon(Icons.edit_note_outlined),
            label: 'Input',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_rounded),
            label: 'Riwayat',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_2_outlined),
            label: 'Perwalian',
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

  void _openTab(int index) {
    setState(() => _selectedIndex = index);
  }

  void _openGradeInput(TeacherAssignment assignment) {
    Navigator.of(context).pushNamed(
      TeacherGradeInputScreen.routeName,
      arguments: TeacherGradeInputArgs(
        classId: assignment.classId,
        subjectId: assignment.subjectId > 0 ? assignment.subjectId : null,
        majlisSubjectId:
            assignment.majlisSubjectId > 0 ? assignment.majlisSubjectId : null,
        title: '${assignment.className} - ${assignment.subjectName}',
      ),
    );
  }

  void _openAttendanceInput(TeacherClassOption item) {
    Navigator.of(context).pushNamed(
      TeacherAttendanceInputScreen.routeName,
      arguments: TeacherAttendanceInputArgs(
        classId: item.id,
        title: 'Absensi ${item.name}',
      ),
    );
  }

  void _openModule(String key, String title, {int? classId}) {
    Navigator.of(context).pushNamed(
      TeacherModuleScreen.routeName,
      arguments: TeacherModuleArgs(
        key: key,
        title: title,
        classId: classId,
      ),
    );
  }
}

class _TeacherHomeTab extends StatelessWidget {
  const _TeacherHomeTab({
    required this.onOpenTab,
    required this.onOpenGradeInput,
    required this.onOpenAttendanceInput,
    required this.onOpenModule,
  });

  final ValueChanged<int> onOpenTab;
  final ValueChanged<TeacherAssignment> onOpenGradeInput;
  final ValueChanged<TeacherClassOption> onOpenAttendanceInput;
  final void Function(String key, String title, {int? classId}) onOpenModule;

  @override
  Widget build(BuildContext context) {
    return _TeacherSectionPage(
      title: 'Dashboard',
      builder: (dashboard) => ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          _TeacherHeader(profile: dashboard.profile),
          const SizedBox(height: 18),
          _SummaryCard(summary: dashboard.summary),
          const SizedBox(height: 22),
          const SectionTitle(title: 'Akses Cepat'),
          const SizedBox(height: 10),
          _QuickShortcutGrid(onOpenTab: onOpenTab),
          const SizedBox(height: 22),
          SectionTitle(
            title: 'Agenda Hari Ini',
            trailing: _InfoBadge(label: dashboard.todayName),
          ),
          const SizedBox(height: 10),
          if (dashboard.todaySchedules.isEmpty)
            const AppEmptyState(
              title: 'Tidak Ada Jadwal Hari Ini',
              subtitle: 'Agenda mengajar hari ini belum tersedia.',
            )
          else
            ...dashboard.todaySchedules.map(
              (item) => _ScheduleTile(
                item: item,
                onTap: () => onOpenGradeInput(
                  TeacherAssignment(
                    classId: item.classId,
                    className: item.className,
                    subjectId: item.subjectId,
                    majlisSubjectId: item.majlisSubjectId,
                    subjectName: item.subjectName,
                  ),
                ),
              ),
            ),
          const SizedBox(height: 22),
          SectionTitle(
            title: 'Pengumuman',
            trailing: _InfoBadge(
              label: '${dashboard.unreadAnnouncementsCount} baru',
            ),
          ),
          const SizedBox(height: 10),
          AnnouncementsSection(
            announcements: dashboard.announcements,
            unreadCount: dashboard.unreadAnnouncementsCount,
            maxItems: 3,
          ),
        ],
      ),
    );
  }
}

class _TeacherInputTab extends StatelessWidget {
  const _TeacherInputTab({
    required this.onOpenTab,
    required this.onOpenGradeInput,
    required this.onOpenAttendanceInput,
    required this.onOpenModule,
  });

  final ValueChanged<int> onOpenTab;
  final ValueChanged<TeacherAssignment> onOpenGradeInput;
  final ValueChanged<TeacherClassOption> onOpenAttendanceInput;
  final void Function(String key, String title, {int? classId}) onOpenModule;

  @override
  Widget build(BuildContext context) {
    return _TeacherSectionPage(
      title: 'Input',
      builder: (dashboard) => ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          const SectionTitle(title: 'Pilih Jenis Input'),
          const SizedBox(height: 10),
          if (dashboard.inputMenu.isEmpty)
            const AppEmptyState(
              title: 'Belum Ada Menu Input',
              subtitle: 'Jenis input untuk guru belum tersedia.',
            )
          else
            _InputMenuGrid(
              items: dashboard.inputMenu,
              onTap: (item) => _handleInputMenuTap(item, dashboard),
            ),
        ],
      ),
    );
  }

  void _handleInputMenuTap(
    TeacherMenuItem item,
    TeacherDashboardModel dashboard,
  ) {
    switch (item.key) {
      case 'nilai':
        if (dashboard.teachingAssignments.isNotEmpty) {
          onOpenGradeInput(dashboard.teachingAssignments.first);
        }
        break;
      case 'absensi':
        if (dashboard.classOptions.isNotEmpty) {
          onOpenAttendanceInput(dashboard.classOptions.first);
        }
        break;
      case 'perilaku':
        onOpenModule('input-behavior', item.label);
        break;
      case 'tahfidz':
        onOpenModule('input-tahfidz', item.label);
        break;
      case 'bacaan':
        onOpenModule('input-recitation', item.label);
        break;
      case 'evaluasi':
        onOpenModule('input-evaluation', item.label);
        break;
      default:
        onOpenTab(2);
        break;
    }
  }
}

class _TeacherHistoryTab extends StatelessWidget {
  const _TeacherHistoryTab({
    required this.onOpenTab,
    required this.onOpenModule,
  });

  final ValueChanged<int> onOpenTab;
  final void Function(String key, String title, {int? classId}) onOpenModule;

  @override
  Widget build(BuildContext context) {
    return _TeacherSectionPage(
      title: 'Riwayat',
      builder: (dashboard) => ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          const SectionTitle(title: 'Setoran Tahfidz Terakhir'),
          const SizedBox(height: 12),
          if (dashboard.recentTahfidz.isEmpty)
            const AppEmptyState(
              title: 'Belum Ada Setoran Tahfidz',
              subtitle: 'Riwayat setoran tahfidz akan tampil di sini.',
            )
          else
            ...dashboard.recentTahfidz.map((item) => _RecordTile(item: item)),
          const SizedBox(height: 18),
          const SectionTitle(title: 'Setoran Bacaan Terakhir'),
          const SizedBox(height: 12),
          if (dashboard.recentRecitation.isEmpty)
            const AppEmptyState(
              title: 'Belum Ada Setoran Bacaan',
              subtitle: 'Riwayat setoran bacaan akan tampil di sini.',
            )
          else
            ...dashboard.recentRecitation
                .map((item) => _RecordTile(item: item)),
          const SizedBox(height: 18),
          const SectionTitle(title: 'Pusat Riwayat'),
          const SizedBox(height: 12),
          ...dashboard.historyMenu.map(
            (item) => _MenuTile(
              item: item,
              onTap: () => onOpenModule(
                item.key == 'riwayat_absensi'
                    ? 'attendance-history'
                    : 'grade-history',
                item.label,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TeacherHomeroomTab extends StatelessWidget {
  const _TeacherHomeroomTab({
    required this.onOpenTab,
    required this.onOpenModule,
  });

  final ValueChanged<int> onOpenTab;
  final void Function(String key, String title, {int? classId}) onOpenModule;

  @override
  Widget build(BuildContext context) {
    return _TeacherSectionPage(
      title: 'Perwalian',
      builder: (dashboard) {
        final homeroom = dashboard.homeroom;
        final fallbackClass = dashboard.classOptions.isNotEmpty
            ? dashboard.classOptions.first
            : null;
        final hasFallbackClass = fallbackClass != null;
        if (!homeroom.available && !hasFallbackClass) {
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(20),
            children: const [
              AppEmptyState(
                title: 'Belum Menjadi Wali Kelas',
                subtitle: 'Data perwalian belum tersedia pada akun ini.',
              ),
            ],
          );
        }

        final classId =
            homeroom.classId > 0 ? homeroom.classId : (fallbackClass?.id ?? 0);
        final className = homeroom.className != '-'
            ? homeroom.className
            : (fallbackClass?.name ?? '-');
        final studentCount = homeroom.available ? homeroom.studentCount : 0;
        final majlisCount = homeroom.available ? homeroom.majlisCount : 0;
        final menu = homeroom.menu.isNotEmpty
            ? homeroom.menu
            : [
                TeacherMenuItem(
                  key: 'homeroom_students',
                  label: 'Data Peserta Kelas',
                  description: 'Lihat data siswa pada kelas yang diampu.',
                ),
                TeacherMenuItem(
                  key: 'class_announcements',
                  label: 'Pengumuman Kelas',
                  description: 'Kelola pengumuman untuk kelas yang diampu.',
                ),
                TeacherMenuItem(
                  key: 'behavior_reports',
                  label: 'Laporan Perilaku',
                  description:
                      'Input catatan perilaku siswa pada kelas yang diampu.',
                ),
              ];

        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionTitle(
                    title: homeroom.available
                        ? 'Ringkasan Perwalian'
                        : 'Ringkasan Kelas Ajar',
                  ),
                  const SizedBox(height: 14),
                  Text(
                    className,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _MetricTile(
                          label: 'Siswa',
                          value: '$studentCount',
                          icon: Icons.school_rounded,
                          accent: const Color(0xFF2563EB),
                          background: const Color(0xFFE8F1FF),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _MetricTile(
                          label: 'Peserta Majelis',
                          value: '$majlisCount',
                          icon: Icons.groups_rounded,
                          accent: const Color(0xFF0F766E),
                          background: const Color(0xFFECFDF5),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            SectionTitle(
              title: homeroom.available ? 'Menu Perwalian' : 'Menu Kelas',
            ),
            const SizedBox(height: 12),
            ...menu.map(
              (item) => _MenuTile(
                item: item,
                onTap: () => onOpenModule(
                  item.key == 'class_announcements'
                      ? 'class-announcements'
                      : item.key == 'homeroom_students'
                          ? 'homeroom-students'
                          : 'input-behavior',
                  item.label,
                  classId: classId > 0 ? classId : null,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _TeacherProfileTab extends StatelessWidget {
  const _TeacherProfileTab();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return _TeacherSectionPage(
      title: 'Profil',
      builder: (dashboard) {
        final authName = auth.currentUser?.name ?? '-';
        final authUsername = auth.currentUser?.username ?? '-';
        final profileName = dashboard.profile.fullName.trim().isNotEmpty &&
                dashboard.profile.fullName.trim() != '-'
            ? dashboard.profile.fullName
            : authName;
        final profileNip = dashboard.profile.nip.trim().isNotEmpty &&
                dashboard.profile.nip.trim() != '-'
            ? dashboard.profile.nip
            : authUsername;

        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(title: 'Profil Guru'),
                  const SizedBox(height: 14),
                  _ProfileRow(label: 'Nama', value: profileName),
                  _ProfileRow(label: 'NIP/Username', value: profileNip),
                  _ProfileRow(
                    label: 'Wali Kelas',
                    value: dashboard.profile.homeroomClassName,
                  ),
                  _ProfileRow(
                    label: 'Total Kelas',
                    value: '${dashboard.profile.totalClasses}',
                  ),
                  _ProfileRow(
                    label: 'Total Siswa',
                    value: '${dashboard.profile.totalStudents}',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(title: 'Kelas Aktif'),
                  const SizedBox(height: 12),
                  if (dashboard.classOptions.isEmpty)
                    const Text(
                      'Belum ada kelas aktif pada akun guru ini.',
                      style: TextStyle(color: Color(0xFF64748B)),
                    )
                  else
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: dashboard.classOptions.map((item) {
                        return Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE8F1FF),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            item.name,
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
            ),
            const SizedBox(height: 12),
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(title: 'Boarding Hari Ini'),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: _MetricTile(
                          label: 'Hadir',
                          value: '${dashboard.summary.boarding.hadir}',
                          icon: Icons.check_circle_rounded,
                          accent: const Color(0xFF0F766E),
                          background: const Color(0xFFECFDF5),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _MetricTile(
                          label: 'Belum input',
                          value: '${dashboard.summary.boarding.belumInput}',
                          icon: Icons.pending_actions_rounded,
                          accent: const Color(0xFFB45309),
                          background: const Color(0xFFFFF6E8),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _MetricTile(
                          label: 'Sakit/Izin',
                          value:
                              '${dashboard.summary.boarding.sakit}/${dashboard.summary.boarding.izin}',
                          icon: Icons.healing_rounded,
                          accent: const Color(0xFF7C3AED),
                          background: const Color(0xFFF3E8FF),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _MetricTile(
                          label: 'Alpa',
                          value: '${dashboard.summary.boarding.alpa}',
                          icon: Icons.error_outline_rounded,
                          accent: const Color(0xFFB91C1C),
                          background: const Color(0xFFFFEEEE),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _TeacherSectionPage extends StatelessWidget {
  const _TeacherSectionPage({
    required this.title,
    required this.builder,
  });

  final String title;
  final Widget Function(TeacherDashboardModel dashboard) builder;

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TeacherDashboardProvider>();
    final dashboard = provider.dashboard;

    if (provider.state == ViewState.loading && dashboard == null) {
      return AppLoadingView(message: 'Memuat $title...');
    }
    if (provider.state == ViewState.error && dashboard == null) {
      return AppErrorState(
        message: provider.errorMessage ?? 'Gagal memuat $title.',
        onRetry: () => provider.fetchDashboard(forceRefresh: true),
      );
    }
    if (dashboard == null) {
      return AppEmptyState(
        title: '$title Belum Tersedia',
        subtitle: 'Belum ada data $title.',
      );
    }

    return RefreshIndicator(
      onRefresh: () => provider.fetchDashboard(forceRefresh: true),
      child: builder(dashboard),
    );
  }
}

class _TeacherHeader extends StatelessWidget {
  const _TeacherHeader({required this.profile});

  final TeacherProfile profile;

  @override
  Widget build(BuildContext context) {
    final hour = DateTime.now().hour;
    final greeting = hour < 11
        ? 'Selamat pagi'
        : hour < 15
            ? 'Selamat siang'
            : hour < 18
                ? 'Selamat sore'
                : 'Selamat malam';

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 26),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF143A6F), Color(0xFF2F80ED)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1F2F80ED),
            blurRadius: 28,
            offset: Offset(0, 16),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            top: -18,
            right: -8,
            child: Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.10),
                shape: BoxShape.circle,
              ),
            ),
          ),
          Positioned(
            bottom: -36,
            left: -24,
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.co_present_rounded,
                      size: 16,
                      color: Colors.white,
                    ),
                    SizedBox(width: 8),
                    Text(
                      'Dashboard Guru',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              Text(
                'Assalamu\'alaikum,',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Colors.white.withValues(alpha: 0.88),
                      fontWeight: FontWeight.w600,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                profile.fullName,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                      height: 1.1,
                    ),
              ),
              const SizedBox(height: 12),
              Text(
                '$greeting. Kelola agenda mengajar, input data, dan perwalian dari satu layar.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.white.withValues(alpha: 0.82),
                      height: 1.45,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final TeacherSummary summary;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(20),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final isCompact = constraints.maxWidth < 360;

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Ringkasan utama',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F1FF),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Text(
                      'Live',
                      style: TextStyle(
                        color: Color(0xFF2563EB),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Pantauan cepat untuk jadwal mengajar dan aktivitas tahfidz hari ini.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: const Color(0xFF64748B),
                      height: 1.45,
                    ),
              ),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                mainAxisExtent: isCompact ? 118 : 110,
                children: [
                  _MetricTile(
                    label: 'Jadwal hari ini',
                    value: '${summary.todayScheduleCount} kelas',
                    icon: Icons.event_note_rounded,
                    accent: const Color(0xFF2563EB),
                    background: const Color(0xFFE8F1FF),
                  ),
                  _MetricTile(
                    label: 'Evaluasi Tahfidz',
                    value: '${summary.todayEvaluationCount} evaluasi',
                    icon: Icons.assignment_turned_in_rounded,
                    accent: const Color(0xFFB45309),
                    background: const Color(0xFFFFF6E8),
                  ),
                  _MetricTile(
                    label: 'Tahfidz',
                    value: '${summary.todayTahfidzCount} setoran',
                    icon: Icons.menu_book_rounded,
                    accent: const Color(0xFF047857),
                    background: const Color(0xFFECFDF5),
                  ),
                  _MetricTile(
                    label: 'Bacaan',
                    value: '${summary.todayRecitationCount} setoran',
                    icon: Icons.auto_stories_rounded,
                    accent: const Color(0xFF0F766E),
                    background: const Color(0xFFEFF6FF),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.accent,
    required this.background,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color accent;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.72),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 18, color: accent),
          ),
          const SizedBox(height: 12),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: const Color(0xFF64748B),
                  fontWeight: FontWeight.w600,
                  fontSize: 11,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF0F172A),
                  fontSize: 12.5,
                  height: 1.2,
                ),
          ),
        ],
      ),
    );
  }
}

class _ScheduleTile extends StatelessWidget {
  const _ScheduleTile({required this.item, required this.onTap});

  final TeacherScheduleItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.subjectName,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 14.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    item.className,
                    style: const TextStyle(
                      color: Color(0xFF64748B),
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    item.timeRange,
                    style: const TextStyle(
                      color: Color(0xFF94A3B8),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
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
              child: const Text(
                'Aktif',
                style: TextStyle(
                  color: Color(0xFF2563EB),
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RecordTile extends StatelessWidget {
  const _RecordTile({required this.item});

  final TeacherRecordItem item;

  @override
  Widget build(BuildContext context) {
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
                  item.participantName,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    fontSize: 14.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  item.detail,
                  style: const TextStyle(
                    color: Color(0xFF64748B),
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  AppDateFormatter.shortDate(item.date),
                  style: const TextStyle(
                    color: Color(0xFF94A3B8),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
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
              '${item.score}',
              style: const TextStyle(
                color: Color(0xFF2563EB),
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({required this.item, required this.onTap});

  final TeacherMenuItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: AppCard(
        margin: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: const Color(0xFFF8FBFF),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(
                Icons.chevron_right_rounded,
                color: Color(0xFF2563EB),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.label,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 14.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    item.description,
                    style: const TextStyle(
                      color: Color(0xFF64748B),
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InputMenuGrid extends StatelessWidget {
  const _InputMenuGrid({
    required this.items,
    required this.onTap,
  });

  final List<TeacherMenuItem> items;
  final ValueChanged<TeacherMenuItem> onTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 360;
        final isNarrow = constraints.maxWidth < 390;

        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: isCompact ? 1 : 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            mainAxisExtent: isCompact ? 152 : (isNarrow ? 164 : 156),
          ),
          itemBuilder: (context, index) {
            final item = items[index];
            final accent = _menuAccentColor(item.key);

            return InkWell(
              borderRadius: BorderRadius.circular(20),
              onTap: () => onTap(item),
              child: Ink(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFD9E4F2)),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x0C0F172A),
                      blurRadius: 18,
                      offset: Offset(0, 8),
                    ),
                  ],
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          color: accent.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Icon(
                          _menuIcon(item.key),
                          color: accent,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        item.label,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontWeight: FontWeight.w800,
                          fontSize: isNarrow ? 13 : 13.5,
                          height: 1.25,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Expanded(
                        child: Text(
                          item.description,
                          maxLines: isCompact ? 3 : 4,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: const Color(0xFF64748B),
                            fontSize: isNarrow ? 11 : 11.5,
                            height: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

IconData _menuIcon(String key) {
  switch (key) {
    case 'nilai':
      return Icons.grading_rounded;
    case 'absensi':
      return Icons.fact_check_rounded;
    case 'perilaku':
      return Icons.shield_outlined;
    case 'tahfidz':
      return Icons.menu_book_rounded;
    case 'bacaan':
      return Icons.auto_stories_rounded;
    case 'evaluasi':
      return Icons.assignment_turned_in_rounded;
    default:
      return Icons.edit_note_rounded;
  }
}

Color _menuAccentColor(String key) {
  switch (key) {
    case 'nilai':
      return const Color(0xFF2563EB);
    case 'absensi':
      return const Color(0xFF0F766E);
    case 'perilaku':
      return const Color(0xFFB91C1C);
    case 'tahfidz':
      return const Color(0xFF047857);
    case 'bacaan':
      return const Color(0xFF7C3AED);
    case 'evaluasi':
      return const Color(0xFFB45309);
    default:
      return const Color(0xFF2563EB);
  }
}

class _QuickShortcutGrid extends StatelessWidget {
  const _QuickShortcutGrid({required this.onOpenTab});

  final ValueChanged<int> onOpenTab;

  @override
  Widget build(BuildContext context) {
    const items = <_ShortcutItem>[
      _ShortcutItem(
        icon: Icons.edit_note_rounded,
        title: 'Input Data',
        tabIndex: 1,
      ),
      _ShortcutItem(
        icon: Icons.history_rounded,
        title: 'Riwayat',
        tabIndex: 2,
      ),
      _ShortcutItem(
        icon: Icons.groups_2_rounded,
        title: 'Perwalian',
        tabIndex: 3,
      ),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 360;

        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: isCompact ? 2 : 3,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            mainAxisExtent: isCompact ? 108 : 94,
          ),
          itemBuilder: (context, index) {
            final item = items[index];
            return InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () => onOpenTab(item.tabIndex),
              child: Ink(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFD9E4F2)),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x0C0F172A),
                      blurRadius: 18,
                      offset: Offset(0, 8),
                    ),
                  ],
                ),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: const Color(0xFFE8F1FF),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Icon(item.icon, color: const Color(0xFF2563EB)),
                      ),
                      const SizedBox(height: 12),
                      Flexible(
                        child: Text(
                          item.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            height: 1.2,
                            fontSize: 12.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _ShortcutItem {
  const _ShortcutItem({
    required this.icon,
    required this.title,
    required this.tabIndex,
  });

  final IconData icon;
  final String title;
  final int tabIndex;
}

class _InfoBadge extends StatelessWidget {
  const _InfoBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: const Color(0xFFE8F1FF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Color(0xFF2563EB),
          fontWeight: FontWeight.w700,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(color: Color(0xFF6B7280)),
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}
