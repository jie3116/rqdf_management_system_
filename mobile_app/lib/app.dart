import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/network/api_client.dart';
import 'core/storage/local_preferences.dart';
import 'core/storage/secure_token_storage.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/data/repositories/auth_repository.dart';
import 'features/auth/data/services/auth_service.dart';
import 'features/auth/presentation/providers/auth_provider.dart';
import 'features/auth/presentation/screens/login_screen.dart';
import 'features/auth/presentation/screens/splash_screen.dart';
import 'features/auth/presentation/utils/auth_navigation.dart';
import 'features/majlis_dashboard/data/repositories/majlis_dashboard_repository.dart';
import 'features/majlis_dashboard/data/services/majlis_dashboard_service.dart';
import 'features/majlis_dashboard/presentation/providers/majlis_dashboard_provider.dart';
import 'features/majlis_dashboard/presentation/screens/majlis_dashboard_screen.dart';
import 'features/parent_dashboard/data/repositories/parent_dashboard_repository.dart';
import 'features/parent_dashboard/data/repositories/parent_feature_repository.dart';
import 'features/parent_dashboard/data/services/parent_dashboard_service.dart';
import 'features/parent_dashboard/data/services/parent_feature_service.dart';
import 'features/parent_dashboard/presentation/providers/dashboard_provider.dart';
import 'features/parent_dashboard/presentation/providers/quick_action_provider.dart';
import 'features/parent_dashboard/presentation/screens/dashboard_screen.dart';
import 'features/parent_dashboard/presentation/screens/feature_placeholder_screen.dart';
import 'features/parent_dashboard/presentation/screens/quick_action_screen.dart';
import 'features/teacher_dashboard/data/repositories/teacher_dashboard_repository.dart';
import 'features/teacher_dashboard/data/repositories/teacher_action_repository.dart';
import 'features/teacher_dashboard/data/services/teacher_action_service.dart';
import 'features/teacher_dashboard/data/services/teacher_dashboard_service.dart';
import 'features/teacher_dashboard/presentation/providers/teacher_dashboard_provider.dart';
import 'features/teacher_dashboard/presentation/screens/teacher_attendance_input_screen.dart';
import 'features/teacher_dashboard/presentation/screens/teacher_dashboard_screen.dart';
import 'features/teacher_dashboard/presentation/screens/teacher_grade_input_screen.dart';
import 'features/teacher_dashboard/presentation/screens/teacher_module_screen.dart';

class RqdfApp extends StatefulWidget {
  const RqdfApp({super.key});

  @override
  State<RqdfApp> createState() => _RqdfAppState();
}

class _RqdfAppState extends State<RqdfApp> {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  StreamSubscription<RemoteMessage>? _onMessageOpenedSubscription;
  final Set<String> _handledNotificationKeys = <String>{};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _registerNotificationOpenHandlers();
    });
  }

  @override
  void dispose() {
    _onMessageOpenedSubscription?.cancel();
    super.dispose();
  }

  Future<void> _registerNotificationOpenHandlers() async {
    _onMessageOpenedSubscription ??=
        FirebaseMessaging.onMessageOpenedApp.listen(_handleNotificationOpened);
    final initialMessage = await FirebaseMessaging.instance.getInitialMessage();
    if (initialMessage != null) {
      await _handleNotificationOpened(initialMessage);
    }
  }

  Future<void> _handleNotificationOpened(RemoteMessage message) async {
    final key = _notificationKey(message);
    if (_handledNotificationKeys.contains(key)) {
      return;
    }
    _handledNotificationKeys.add(key);
    if (!mounted) {
      return;
    }

    final ctx = _navigatorKey.currentContext;
    final nav = _navigatorKey.currentState;
    if (ctx == null || nav == null) {
      return;
    }

    final authProvider = ctx.read<AuthProvider>();
    if (!authProvider.isAuthenticated) {
      return;
    }

    await _refreshDashboardByRole(ctx, authProvider);
    if (!mounted) {
      return;
    }
    final targetRoute = AuthNavigation.routeForUser(authProvider.currentUser);
    nav.pushNamedAndRemoveUntil(targetRoute, (_) => false);
  }

  Future<void> _refreshDashboardByRole(
    BuildContext context,
    AuthProvider authProvider,
  ) async {
    final user = authProvider.currentUser;
    if (user?.isTeacher == true) {
      await context
          .read<TeacherDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
      return;
    }
    if (user?.isMajlisParticipant == true) {
      await context
          .read<MajlisDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
      return;
    }
    await context.read<DashboardProvider>().fetchDashboard(forceRefresh: true);
  }

  String _notificationKey(RemoteMessage message) {
    final announcementId = (message.data['announcement_id'] ?? '').toString();
    final sentTs = message.sentTime?.millisecondsSinceEpoch ?? 0;
    return message.messageId ?? '$sentTs:$announcementId';
  }

  @override
  Widget build(BuildContext context) {
    final tokenStorage = SecureTokenStorage();
    final preferencesStorage = LocalPreferencesStorage();
    final apiClient = ApiClient(tokenStorage: tokenStorage);
    final authService = AuthService(apiClient: apiClient);
    final authRepository = AuthRepository(
      authService: authService,
      tokenStorage: tokenStorage,
      preferencesStorage: preferencesStorage,
    );
    final dashboardService = ParentDashboardService(apiClient: apiClient);
    final dashboardRepository = ParentDashboardRepository(dashboardService);
    final majlisDashboardService = MajlisDashboardService(apiClient: apiClient);
    final majlisDashboardRepository =
        MajlisDashboardRepository(majlisDashboardService);
    final featureService = ParentFeatureService(apiClient: apiClient);
    final featureRepository = ParentFeatureRepository(featureService);
    final teacherDashboardService =
        TeacherDashboardService(apiClient: apiClient);
    final teacherDashboardRepository =
        TeacherDashboardRepository(teacherDashboardService);
    final teacherActionService = TeacherActionService(apiClient: apiClient);
    final teacherActionRepository =
        TeacherActionRepository(teacherActionService);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>(
          create: (_) => AuthProvider(
            authRepository: authRepository,
            apiClient: apiClient,
          ),
        ),
        ChangeNotifierProxyProvider<AuthProvider, DashboardProvider>(
          create: (_) => DashboardProvider(
            dashboardRepository: dashboardRepository,
          ),
          update: (_, authProvider, dashboardProvider) => (dashboardProvider ??
              DashboardProvider(dashboardRepository: dashboardRepository))
            ..setSession(
              isAuthenticated: authProvider.isAuthenticated,
              userName: authProvider.currentUser?.name,
            ),
        ),
        ChangeNotifierProxyProvider<AuthProvider, MajlisDashboardProvider>(
          create: (_) => MajlisDashboardProvider(
            repository: majlisDashboardRepository,
          ),
          update: (_, authProvider, dashboardProvider) => (dashboardProvider ??
              MajlisDashboardProvider(
                repository: majlisDashboardRepository,
              ))
            ..setSession(isAuthenticated: authProvider.isAuthenticated),
        ),
        ChangeNotifierProxyProvider<AuthProvider, TeacherDashboardProvider>(
          create: (_) => TeacherDashboardProvider(
            repository: teacherDashboardRepository,
          ),
          update: (_, authProvider, dashboardProvider) => (dashboardProvider ??
              TeacherDashboardProvider(
                repository: teacherDashboardRepository,
              ))
            ..setSession(isAuthenticated: authProvider.isAuthenticated),
        ),
        Provider<TeacherActionRepository>.value(value: teacherActionRepository),
        Provider<ParentFeatureRepository>.value(value: featureRepository),
      ],
      child: MaterialApp(
        navigatorKey: _navigatorKey,
        title: 'RQDF Management System',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        initialRoute: SplashScreen.routeName,
        onGenerateRoute: (settings) {
          switch (settings.name) {
            case SplashScreen.routeName:
              return MaterialPageRoute<void>(
                builder: (_) => const SplashScreen(),
              );
            case LoginScreen.routeName:
              return MaterialPageRoute<void>(
                builder: (_) => const LoginScreen(),
              );
            case DashboardScreen.routeName:
              return MaterialPageRoute<void>(
                builder: (_) => const DashboardScreen(),
              );
            case MajlisDashboardScreen.routeName:
              return MaterialPageRoute<void>(
                builder: (_) => const MajlisDashboardScreen(),
              );
            case TeacherDashboardScreen.routeName:
              return MaterialPageRoute<void>(
                builder: (_) => const TeacherDashboardScreen(),
              );
            case TeacherGradeInputScreen.routeName:
              final args = settings.arguments as TeacherGradeInputArgs;
              return MaterialPageRoute<void>(
                builder: (_) => TeacherGradeInputScreen(args: args),
              );
            case TeacherAttendanceInputScreen.routeName:
              final args = settings.arguments as TeacherAttendanceInputArgs;
              return MaterialPageRoute<void>(
                builder: (_) => TeacherAttendanceInputScreen(args: args),
              );
            case TeacherModuleScreen.routeName:
              final args = settings.arguments as TeacherModuleArgs;
              return MaterialPageRoute<void>(
                builder: (_) => TeacherModuleScreen(args: args),
              );
            case FeaturePlaceholderScreen.routeName:
              final title = settings.arguments is String
                  ? settings.arguments! as String
                  : 'Fitur';
              return MaterialPageRoute<void>(
                builder: (_) => FeaturePlaceholderScreen(title: title),
              );
            case QuickActionScreen.routeName:
              final args = settings.arguments as QuickActionScreenArgs?;
              if (args == null) {
                return MaterialPageRoute<void>(
                  builder: (_) =>
                      const FeaturePlaceholderScreen(title: 'Fitur'),
                );
              }
              return MaterialPageRoute<void>(
                builder: (_) => ChangeNotifierProvider<QuickActionProvider>(
                  create: (context) => QuickActionProvider(
                    repository: context.read<ParentFeatureRepository>(),
                  ),
                  child: QuickActionScreen(args: args),
                ),
              );
            default:
              return MaterialPageRoute<void>(
                builder: (_) => const SplashScreen(),
              );
          }
        },
      ),
    );
  }
}
