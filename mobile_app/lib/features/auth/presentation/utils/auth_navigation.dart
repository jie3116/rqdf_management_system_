import '../../../majlis_dashboard/presentation/screens/majlis_dashboard_screen.dart';
import '../../../boarding_dashboard/presentation/screens/boarding_dashboard_screen.dart';
import '../../../parent_dashboard/presentation/screens/dashboard_screen.dart';
import '../../../teacher_dashboard/presentation/screens/teacher_dashboard_screen.dart';
import '../../data/models/user_model.dart';
import '../screens/login_screen.dart';

class AuthNavigation {
  const AuthNavigation._();

  static String routeForUser(UserModel? user) {
    if (user == null) {
      return LoginScreen.routeName;
    }
    final activeRole = user.activeRoleKey;
    if (activeRole == 'teacher') {
      return TeacherDashboardScreen.routeName;
    }
    if (activeRole == 'wali_asrama') {
      return BoardingDashboardScreen.routeName;
    }
    if (activeRole == 'majlis_participant') {
      return MajlisDashboardScreen.routeName;
    }
    return DashboardScreen.routeName;
  }
}
