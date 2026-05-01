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
import '../../../parent_dashboard/data/models/announcement_model.dart';
import '../../../parent_dashboard/data/models/quick_action_model.dart';
import '../../../parent_dashboard/data/models/recent_activity_model.dart';
import '../../../parent_dashboard/presentation/widgets/announcements_section.dart';
import '../../../parent_dashboard/presentation/widgets/quick_action_grid.dart';
import '../../../parent_dashboard/presentation/widgets/recent_activities_section.dart';
import '../../data/models/majlis_dashboard_model.dart';
import '../providers/majlis_dashboard_provider.dart';

class MajlisDashboardScreen extends StatefulWidget {
  const MajlisDashboardScreen({super.key});

  static const String routeName = '/majlis-dashboard';

  @override
  State<MajlisDashboardScreen> createState() => _MajlisDashboardScreenState();
}

class _MajlisDashboardScreenState extends State<MajlisDashboardScreen> {
  int _selectedIndex = 0;
  MajlisDashboardProvider? _dashboardProvider;
  int _lastAnnouncementSignal = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<MajlisDashboardProvider>().fetchDashboard();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final provider = context.read<MajlisDashboardProvider>();
    if (!identical(_dashboardProvider, provider)) {
      _dashboardProvider?.removeListener(_onDashboardProviderChanged);
      _dashboardProvider = provider;
      _lastAnnouncementSignal = provider.announcementSignal;
      provider.addListener(_onDashboardProviderChanged);
    }
  }

  @override
  void dispose() {
    _dashboardProvider?.removeListener(_onDashboardProviderChanged);
    super.dispose();
  }

  void _onDashboardProviderChanged() {
    if (!mounted) return;
    final provider = _dashboardProvider;
    if (provider == null) return;
    if (provider.announcementSignal == _lastAnnouncementSignal) return;

    _lastAnnouncementSignal = provider.announcementSignal;
    final delta = provider.lastAnnouncementDelta;
    if (delta <= 0) return;

    final label = delta == 1
        ? 'Ada 1 pengumuman baru.'
        : 'Ada $delta pengumuman baru.';
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
        title: const Text('RQDF Mobile', style: TextStyle(fontWeight: FontWeight.w700)),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            onPressed: () async {
              final navigator = Navigator.of(context);
              await context.read<AuthProvider>().logout();
              if (!mounted) return;
              navigator.pushNamedAndRemoveUntil(LoginScreen.routeName, (_) => false);
            },
          ),
        ],
      ),
      body: IndexedStack(
        index: _selectedIndex,
        children: [
          _HomeTab(
            onTapQuickAction: _handleQuickAction,
          ),
          const _TahfidzPage(),
          const _AbsensiPage(),
          const _JadwalPage(),
          const _ProfilPage(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        height: 74,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        indicatorColor: const Color(0xFFE8F1FF),
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) => setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), label: 'Tahfidz'),
          NavigationDestination(icon: Icon(Icons.fact_check_outlined), label: 'Absensi'),
          NavigationDestination(icon: Icon(Icons.calendar_today_outlined), label: 'Jadwal'),
          NavigationDestination(icon: Icon(Icons.person_outline_rounded), label: 'Profil'),
        ],
      ),
    );
  }

  void _handleQuickAction(QuickActionModel action) {
    if (action.key == 'pengumuman') {
      context.read<MajlisDashboardProvider>().markAnnouncementsRead();
      final dashboard = context.read<MajlisDashboardProvider>().dashboard;
      if (dashboard == null) return;
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => _AnnouncementsPage(dashboard: dashboard),
        ),
      );
      return;
    }
    if (action.key == 'tahfidz') {
      setState(() => _selectedIndex = 1);
      return;
    }
    if (action.key == 'absensi') {
      setState(() => _selectedIndex = 2);
      return;
    }
    if (action.key == 'jadwal') {
      setState(() => _selectedIndex = 3);
      return;
    }
    if (action.key == 'evaluasi') {
      final dashboard = context.read<MajlisDashboardProvider>().dashboard;
      if (dashboard == null) return;
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => _EvaluationPage(dashboard: dashboard),
        ),
      );
      return;
    }
    if (action.key == 'profil') {
      setState(() => _selectedIndex = 4);
    }
  }
}

class _HomeTab extends StatelessWidget {
  const _HomeTab({
    required this.onTapQuickAction,
  });

  final ValueChanged<QuickActionModel> onTapQuickAction;

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MajlisDashboardProvider>();
    final dashboard = provider.dashboard;

    return RefreshIndicator(
      onRefresh: () => provider.fetchDashboard(forceRefresh: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          if (provider.state == ViewState.loading && dashboard == null)
            const SizedBox(height: 120, child: AppLoadingView(message: 'Memuat dashboard...'))
          else if (provider.state == ViewState.error && dashboard == null)
            AppErrorState(
              message: provider.errorMessage ?? 'Terjadi kesalahan.',
              onRetry: () => provider.fetchDashboard(forceRefresh: true),
            )
          else if (dashboard == null)
            const AppEmptyState(
              title: 'Data Dashboard Kosong',
              subtitle: 'Belum ada data dashboard untuk akun ini.',
            )
          else ...[
            _MajlisHeader(profile: dashboard.profile),
            const SizedBox(height: 18),
            _RingkasanCard(dashboard: dashboard),
            const SizedBox(height: 22),
            const SectionTitle(title: 'Akses Cepat'),
            const SizedBox(height: 12),
            QuickActionGrid(
              actions: _quickActions,
              onTapAction: onTapQuickAction,
            ),
            const SizedBox(height: 22),
            SectionTitle(
              title: 'Pengumuman',
              trailing: TextButton(
                onPressed: provider.markAnnouncementsRead,
                child: const Text('Tandai dibaca'),
              ),
            ),
            const SizedBox(height: 10),
            AnnouncementsSection(
              announcements: _announcements(dashboard),
              unreadCount: dashboard.unreadAnnouncementsCount,
              maxItems: 3,
            ),
            const SizedBox(height: 22),
            const SectionTitle(title: 'Aktivitas Terbaru'),
            const SizedBox(height: 10),
            RecentActivitiesSection(
              activities: _recentActivities(dashboard),
              maxItems: 3,
            ),
          ],
        ],
      ),
    );
  }

}

class _TahfidzPage extends StatelessWidget {
  const _TahfidzPage();

  @override
  Widget build(BuildContext context) => _MajlisSectionPage(
        title: 'Tahfidz',
        builder: (dashboard) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SectionTitle(title: 'Riwayat Setoran Hafalan'),
            const SizedBox(height: 12),
            if (dashboard.tahfidzRecords.isEmpty)
              const AppEmptyState(
                title: 'Belum Ada Setoran Hafalan',
                subtitle: 'Riwayat setoran hafalan akan tampil di sini.',
              )
            else
              ...dashboard.tahfidzRecords.map((r) => _InfoTile(
                    title: r.surah,
                    subtitle: '${r.typeLabel} • Ayat ${r.ayatRange} • ${r.quality}',
                    meta: r.date,
                    trailing: '${r.score}',
                  )),
            const SizedBox(height: 18),
            const SectionTitle(title: 'Riwayat Setoran Bacaan'),
            const SizedBox(height: 12),
            if (dashboard.recitationRecords.isEmpty)
              const AppEmptyState(
                title: 'Belum Ada Riwayat Bacaan',
                subtitle: 'Riwayat setoran bacaan akan tampil di sini.',
              )
            else
              ...dashboard.recitationRecords.map((r) => _InfoTile(
                    title: r.materialText,
                    subtitle: r.sourceLabel,
                    meta: r.date,
                    trailing: '${r.score}',
                  )),
            const SizedBox(height: 18),
            const SectionTitle(title: 'Ringkasan Evaluasi'),
            const SizedBox(height: 12),
            if (dashboard.evaluationRecords.isEmpty)
              const AppEmptyState(
                title: 'Belum Ada Evaluasi',
                subtitle: 'Data evaluasi akan tampil di sini.',
              )
            else
              ...dashboard.evaluationRecords.take(3).map((r) => _InfoTile(
                    title: r.periodText,
                    subtitle: 'Makhraj ${r.makhrajErrors} • Tajwid ${r.tajwidErrors} • Harakat ${r.harakatErrors}',
                    meta: r.date,
                    trailing: '${r.score}',
                  )),
          ],
        ),
      );
}

class _AbsensiPage extends StatelessWidget {
  const _AbsensiPage();

  @override
  Widget build(BuildContext context) => _MajlisSectionPage(
        title: 'Absensi',
        builder: (dashboard) {
          final recap = dashboard.attendance.recap;
          return Column(
            children: [
              Row(
                children: [
                  Expanded(child: _MetricCard(label: 'Hadir', value: '${recap.hadir}')),
                  const SizedBox(width: 10),
                  Expanded(child: _MetricCard(label: 'Izin', value: '${recap.izin}')),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(child: _MetricCard(label: 'Sakit', value: '${recap.sakit}')),
                  const SizedBox(width: 10),
                  Expanded(child: _MetricCard(label: 'Alpa', value: '${recap.alpa}')),
                ],
              ),
              const SizedBox(height: 16),
              ...dashboard.attendance.records.map((r) => _InfoTile(
                    title: r.statusLabel,
                    subtitle: '${r.className} • ${r.teacherName}',
                    meta: r.date,
                  )),
            ],
          );
        },
      );
}

class _JadwalPage extends StatelessWidget {
  const _JadwalPage();

  @override
  Widget build(BuildContext context) => _MajlisSectionPage(
        title: 'Jadwal',
        builder: (dashboard) => Column(
          children: dashboard.scheduleDays
              .map((day) => AppCard(
                    margin: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(day.day, style: const TextStyle(fontWeight: FontWeight.w800)),
                        const SizedBox(height: 10),
                        if (day.items.isEmpty)
                          const Text('Belum ada jadwal.', style: TextStyle(color: Color(0xFF64748B)))
                        else
                          ...day.items.map((item) => Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Text('${item.startTime} • ${item.subjectName} • ${item.teacherName}'),
                              )),
                      ],
                    ),
                  ))
              .toList(),
        ),
      );
}

class _ProfilPage extends StatelessWidget {
  const _ProfilPage();

  @override
  Widget build(BuildContext context) => _MajlisSectionPage(
        title: 'Profil',
        builder: (dashboard) => Column(
          children: [
            AppCard(
              child: Column(
                children: [
                  _ProfileRow(label: 'Nama', value: dashboard.profile.fullName),
                  _ProfileRow(label: 'Kelas', value: dashboard.profile.majlisClassName),
                  _ProfileRow(label: 'No. HP', value: dashboard.profile.phone),
                  _ProfileRow(label: 'Pekerjaan', value: dashboard.profile.job),
                  _ProfileRow(label: 'Alamat', value: dashboard.profile.address),
                ],
              ),
            ),
          ],
        ),
      );
}

class _AnnouncementsPage extends StatelessWidget {
  const _AnnouncementsPage({required this.dashboard});

  final MajlisDashboardModel dashboard;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F7FC),
      appBar: AppBar(title: const Text('Pengumuman')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          AnnouncementsSection(
            announcements: _announcements(dashboard),
            unreadCount: dashboard.unreadAnnouncementsCount,
          ),
        ],
      ),
    );
  }
}

class _EvaluationPage extends StatelessWidget {
  const _EvaluationPage({required this.dashboard});

  final MajlisDashboardModel dashboard;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F7FC),
      appBar: AppBar(title: const Text('Evaluasi')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const SectionTitle(title: 'Riwayat Evaluasi'),
          const SizedBox(height: 12),
          if (dashboard.evaluationRecords.isEmpty)
            const AppEmptyState(
              title: 'Belum Ada Evaluasi',
              subtitle: 'Data evaluasi akan tampil di sini.',
            )
          else
            ...dashboard.evaluationRecords.map((r) => _InfoTile(
                  title: r.periodText,
                  subtitle: 'Makhraj ${r.makhrajErrors} • Tajwid ${r.tajwidErrors} • Harakat ${r.harakatErrors}',
                  meta: r.date,
                  trailing: '${r.score}',
                )),
        ],
      ),
    );
  }
}

class _MajlisSectionPage extends StatelessWidget {
  const _MajlisSectionPage({required this.title, required this.builder});

  final String title;
  final Widget Function(MajlisDashboardModel dashboard) builder;

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<MajlisDashboardProvider>();
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
      return AppEmptyState(title: '$title Belum Tersedia', subtitle: 'Belum ada data $title.');
    }
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(20),
      children: [
        SectionTitle(title: title),
        const SizedBox(height: 12),
        builder(dashboard),
      ],
    );
  }
}

class _MajlisHeader extends StatelessWidget {
  const _MajlisHeader({required this.profile});

  final MajlisProfile profile;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 26),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF143A6F), Color(0xFF2F80ED)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(999),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.groups_rounded, size: 16, color: Colors.white),
                SizedBox(width: 8),
                Text('Dashboard Peserta Majelis', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Text('Assalamu\'alaikum,', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white70, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(profile.fullName, style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          Text(
            'Pantau hafalan, kegiatan, dan pengumuman majelis dari satu layar.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white70, height: 1.45),
          ),
        ],
      ),
    );
  }
}

class _RingkasanCard extends StatelessWidget {
  const _RingkasanCard({required this.dashboard});

  final MajlisDashboardModel dashboard;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionTitle(title: 'Ringkasan'),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _MetricCard(label: 'Hafalan', value: dashboard.summary.lastTargetText)),
              const SizedBox(width: 10),
              Expanded(child: _MetricCard(label: 'Total juz', value: '${dashboard.summary.totalJuz}')),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _MetricCard(label: 'Kehadiran', value: '${dashboard.attendance.recap.hadir} hadir')),
              const SizedBox(width: 10),
              Expanded(child: _MetricCard(label: 'Kelas', value: dashboard.profile.majlisClassName)),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FBFF),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFD9E4F2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Color(0xFF64748B), fontSize: 12, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(value, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({required this.title, required this.subtitle, required this.meta, this.trailing});

  final String title;
  final String subtitle;
  final String meta;
  final String? trailing;

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
                Text(title, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14.5)),
                const SizedBox(height: 4),
                Text(subtitle, style: const TextStyle(color: Color(0xFF64748B), height: 1.4)),
                const SizedBox(height: 8),
                Text(AppDateFormatter.shortDate(meta), style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
          if ((trailing ?? '').isNotEmpty) ...[
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(color: const Color(0xFFE8F1FF), borderRadius: BorderRadius.circular(999)),
              child: Text(trailing!, style: const TextStyle(color: Color(0xFF2563EB), fontWeight: FontWeight.w800)),
            ),
          ],
        ],
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Expanded(child: Text(label, style: const TextStyle(color: Color(0xFF6B7280)))),
          const SizedBox(width: 8),
          Flexible(child: Text(value, textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}

List<AnnouncementModel> _announcements(MajlisDashboardModel dashboard) => dashboard.announcements
    .map((item) => AnnouncementModel(
          id: item.id,
          title: item.title,
          content: item.content,
          authorLabel: item.authorLabel,
          createdAt: item.createdAt,
          isUnread: item.isUnread,
        ))
    .toList();

List<RecentActivityModel> _recentActivities(MajlisDashboardModel dashboard) {
  final items = <RecentActivityModel>[];
  if (dashboard.attendance.records.isNotEmpty) {
    final record = dashboard.attendance.records.first;
    items.add(RecentActivityModel(
      type: 'info',
      message: 'Absensi terakhir: ${record.statusLabel} pada ${AppDateFormatter.shortDate(record.date)}',
      createdAt: record.date,
    ));
  }
  if (dashboard.tahfidzRecords.isNotEmpty) {
    final record = dashboard.tahfidzRecords.first;
    items.add(RecentActivityModel(
      type: 'success',
      message: 'Setoran hafalan terakhir: ${record.surah} (${record.score})',
      createdAt: record.date,
    ));
  }
  if (dashboard.evaluationRecords.isNotEmpty) {
    final record = dashboard.evaluationRecords.first;
    items.add(RecentActivityModel(
      type: 'warning',
      message: 'Evaluasi terbaru: ${record.periodText} (${record.score})',
      createdAt: record.date,
    ));
  }
  return items;
}

const List<QuickActionModel> _quickActions = [
  QuickActionModel(key: 'pengumuman', label: 'Pengumuman'),
  QuickActionModel(key: 'tahfidz', label: 'Tahfidz'),
  QuickActionModel(key: 'absensi', label: 'Absensi'),
  QuickActionModel(key: 'jadwal', label: 'Jadwal'),
  QuickActionModel(key: 'evaluasi', label: 'Evaluasi'),
  QuickActionModel(key: 'profil', label: 'Profil'),
];
