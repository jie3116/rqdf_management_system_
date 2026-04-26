import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:rq_mobile/features/parent_dashboard/data/models/parent_dashboard_model.dart';
import 'package:rq_mobile/features/parent_dashboard/data/repositories/parent_dashboard_repository.dart';
import 'package:rq_mobile/features/parent_dashboard/presentation/providers/dashboard_provider.dart';
import 'package:rq_mobile/shared/models/view_state.dart';

class _MockParentDashboardRepository extends Mock
    implements ParentDashboardRepository {}

void main() {
  late _MockParentDashboardRepository repository;
  late DashboardProvider provider;

  setUp(() {
    repository = _MockParentDashboardRepository();
    provider = DashboardProvider(dashboardRepository: repository);
    provider.setSession(isAuthenticated: true, userName: 'Aji');
  });

  test('fetchDashboard success updates state and selected child', () async {
    final mockDashboard = ParentDashboardModel.fromJson({
      'guardian_name': 'Aji Abdul Aziz',
      'selected_child': {
        'id': 10,
        'name': 'Sakhiya',
        'class_name': 'TD Sore',
      },
      'summary': {
        'billing_total': 0,
        'violation_points': 0,
        'memorization_progress': '-',
        'attendance_status': 'Tidak ada absensi hari ini',
      },
      'children': [
        {
          'id': 10,
          'name': 'Sakhiya',
          'class_name': 'TD Sore',
        },
      ],
      'quick_actions': [],
      'recent_activities': [],
      'announcements': [],
      'unread_announcements_count': 0,
    });

    when(() => repository.getDashboard(studentId: any(named: 'studentId')))
        .thenAnswer((_) async => mockDashboard);

    await provider.fetchDashboard(forceRefresh: true);

    expect(provider.state, ViewState.success);
    expect(provider.dashboard?.guardianName, 'Aji Abdul Aziz');
    expect(provider.selectedChild?.id, 10);
    verify(() => repository.getDashboard(studentId: any(named: 'studentId')))
        .called(1);
  });

  test('fetchDashboard failure updates error state', () async {
    when(() => repository.getDashboard(studentId: any(named: 'studentId')))
        .thenThrow(Exception('boom'));

    await provider.fetchDashboard(forceRefresh: true);

    expect(provider.state, ViewState.error);
    expect(provider.errorMessage, isNotNull);
  });
}
