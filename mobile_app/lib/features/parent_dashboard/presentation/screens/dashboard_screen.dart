import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../../shared/models/view_state.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../../../../shared/widgets/app_empty_state.dart';
import '../../../../../shared/widgets/app_error_state.dart';
import '../../../../../shared/widgets/app_loading_view.dart';
import '../../../../../shared/widgets/section_title.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../auth/presentation/screens/login_screen.dart';
import '../../../majlis_dashboard/presentation/screens/majlis_dashboard_screen.dart';
import '../../data/models/quick_action_model.dart';
import '../../data/repositories/parent_feature_repository.dart';
import '../providers/dashboard_provider.dart';
import '../providers/quick_action_provider.dart';
import '../widgets/dashboard_header.dart';
import '../widgets/announcements_section.dart';
import '../widgets/quick_action_grid.dart';
import '../widgets/recent_activities_section.dart';
import '../widgets/student_switcher_card.dart';
import '../widgets/summary_card.dart';
import 'quick_action_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  static const String routeName = '/dashboard';

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with WidgetsBindingObserver {
  DashboardProvider? _dashboardProvider;
  int _lastAnnouncementSignal = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().fetchDashboard();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final provider = context.read<DashboardProvider>();
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
      context.read<DashboardProvider>().fetchDashboard(forceRefresh: true);
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
    final dashboardProvider = context.watch<DashboardProvider>();

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
        index: dashboardProvider.selectedBottomNavIndex,
        children: [
          _HomeTab(onTapQuickAction: _onTapQuickAction),
          _BottomFeatureTab(
            action: const QuickActionModel(key: 'nilai', label: 'Akademik'),
            childId: dashboardProvider.selectedChild?.id,
          ),
          _BottomFeatureTab(
            action: const QuickActionModel(key: 'absensi', label: 'Absensi'),
            childId: dashboardProvider.selectedChild?.id,
          ),
          _BottomFeatureTab(
            action: const QuickActionModel(key: 'keuangan', label: 'Keuangan'),
            childId: dashboardProvider.selectedChild?.id,
          ),
          const _ProfileTab(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        height: 74,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        indicatorColor: const Color(0xFFE8F1FF),
        selectedIndex: dashboardProvider.selectedBottomNavIndex,
        onDestinationSelected: dashboardProvider.setBottomNav,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(
              icon: Icon(Icons.school_outlined), label: 'Akademik'),
          NavigationDestination(
              icon: Icon(Icons.fact_check_outlined), label: 'Absensi'),
          NavigationDestination(
              icon: Icon(Icons.account_balance_wallet_outlined),
              label: 'Keuangan'),
          NavigationDestination(
              icon: Icon(Icons.person_outline_rounded), label: 'Profil'),
        ],
      ),
    );
  }

  void _onTapQuickAction(QuickActionModel action) {
    final selectedChildId = context.read<DashboardProvider>().selectedChild?.id;
    Navigator.of(context).pushNamed(
      QuickActionScreen.routeName,
      arguments: QuickActionScreenArgs(
        action: action,
        childId: selectedChildId,
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

class _HomeTab extends StatelessWidget {
  const _HomeTab({required this.onTapQuickAction});

  final ValueChanged<QuickActionModel> onTapQuickAction;

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<DashboardProvider>();
    final state = provider.state;
    final dashboard = provider.dashboard;

    return RefreshIndicator(
      onRefresh: () => provider.fetchDashboard(forceRefresh: true),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          DashboardHeader(guardianName: provider.greetingName),
          const SizedBox(height: 18),
          if (state == ViewState.loading) ...[
            const SizedBox(
              height: 120,
              child: AppLoadingView(message: 'Memuat dashboard...'),
            ),
          ] else if (state == ViewState.error) ...[
            AppErrorState(
              message: provider.errorMessage ?? 'Terjadi kesalahan.',
              onRetry: () => provider.fetchDashboard(forceRefresh: true),
            ),
          ] else if (dashboard == null) ...[
            const AppEmptyState(
              title: 'Data Dashboard Kosong',
              subtitle: 'Belum ada data dashboard untuk akun ini.',
            ),
          ] else ...[
            if (dashboard.isMajlisParticipant) ...[
              _MajlisSwitchCard(
                onTap: () => Navigator.of(context).pushNamed(
                  MajlisDashboardScreen.routeName,
                ),
              ),
              const SizedBox(height: 14),
            ],
            StudentSwitcherCard(
              selectedChild: provider.selectedChild,
              children: dashboard.children,
              onChanged: (child) => provider.selectChild(child),
            ),
            const SizedBox(height: 18),
            SummaryCard(
              summary: dashboard.summary,
            ),
            const SizedBox(height: 22),
            const SectionTitle(title: 'Akses Cepat'),
            const SizedBox(height: 12),
            QuickActionGrid(
              actions: dashboard.quickActions,
              onTapAction: onTapQuickAction,
            ),
            const SizedBox(height: 22),
            SectionTitle(
              title: 'Pengumuman',
              trailing: TextButton(
                onPressed: () => onTapQuickAction(
                  const QuickActionModel(
                    key: 'pengumuman',
                    label: 'Pengumuman',
                  ),
                ),
                child: const Text('Lihat semua'),
              ),
            ),
            const SizedBox(height: 10),
            AnnouncementsSection(
              announcements: dashboard.announcements,
              unreadCount: dashboard.unreadAnnouncementsCount,
              maxItems: 3,
            ),
            const SizedBox(height: 22),
            const SectionTitle(title: 'Aktivitas Terbaru'),
            const SizedBox(height: 10),
            RecentActivitiesSection(
              activities: dashboard.recentActivities,
              maxItems: 3,
            ),
          ],
        ],
      ),
    );
  }
}

class _MajlisSwitchCard extends StatelessWidget {
  const _MajlisSwitchCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: onTap,
      child: AppCard(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFFE8F1FF), Color(0xFFD7E8FF)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(18),
              ),
              child: const Icon(
                Icons.groups_rounded,
                color: Color(0xFF2563EB),
              ),
            ),
            const SizedBox(width: 14),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Akses tambahan',
                    style: TextStyle(
                      color: Color(0xFF64748B),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Masuk Dashboard Majelis',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                    ),
                  ),
                  SizedBox(height: 3),
                  Text(
                    'Buka data majelis ta\'lim untuk akun ini.',
                    style: TextStyle(color: Color(0xFF64748B)),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFE8F1FF),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.arrow_forward_rounded,
                color: Color(0xFF2563EB),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BottomFeatureTab extends StatelessWidget {
  const _BottomFeatureTab({
    required this.action,
    required this.childId,
  });

  final QuickActionModel action;
  final int? childId;

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<QuickActionProvider>(
      create: (context) => QuickActionProvider(
        repository: context.read<ParentFeatureRepository>(),
      ),
      child: QuickActionContent(
        action: action,
        childId: childId,
      ),
    );
  }
}

class _ProfileTab extends StatelessWidget {
  const _ProfileTab();

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<DashboardProvider>();
    final dashboard = provider.dashboard;
    final selectedChild = provider.selectedChild;

    if (provider.state == ViewState.loading && dashboard == null) {
      return const AppLoadingView(message: 'Memuat profil...');
    }

    if (provider.state == ViewState.error && dashboard == null) {
      return AppErrorState(
        message: provider.errorMessage ?? 'Gagal memuat profil.',
        onRetry: () => provider.fetchDashboard(forceRefresh: true),
      );
    }

    if (selectedChild == null) {
      return const AppEmptyState(
        title: 'Profil Belum Tersedia',
        subtitle: 'Pilih data anak di tab Home untuk melihat profil.',
      );
    }

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(20),
      children: [
        AppCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionTitle(title: 'Profil Wali'),
              const SizedBox(height: 14),
              Row(
                children: [
                  Container(
                    width: 54,
                    height: 54,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF143A6F), Color(0xFF2F80ED)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Center(
                      child: Text(
                        provider.greetingName.isNotEmpty
                            ? provider.greetingName[0].toUpperCase()
                            : 'W',
                        style: const TextStyle(
                          color: Colors.white,
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
                        Text(
                          provider.greetingName,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Akun orang tua aktif',
                          style: TextStyle(color: Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        AppCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionTitle(title: 'Profil Anak'),
              const SizedBox(height: 14),
              _ProfileRow(label: 'Nama', value: selectedChild.name),
              _ProfileRow(
                label: 'ID Anak',
                value: '${selectedChild.id}',
              ),
              _ProfileRow(label: 'Kelas', value: selectedChild.className),
            ],
          ),
        ),
        const SizedBox(height: 12),
        const AppCard(
          padding: EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionTitle(title: 'Ringkasan Akses'),
              SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: _ProfileMetricTile(
                      label: 'Menu cepat',
                      value: '7 modul',
                    ),
                  ),
                  SizedBox(width: 10),
                  Expanded(
                    child: _ProfileMetricTile(
                      label: 'Tab aktif',
                      value: 'Profil',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
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

class _ProfileMetricTile extends StatelessWidget {
  const _ProfileMetricTile({
    required this.label,
    required this.value,
  });

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
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFF64748B),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
