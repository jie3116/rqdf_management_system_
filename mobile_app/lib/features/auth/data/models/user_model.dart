import '../../../../core/utils/json_helper.dart';

class UserModel {
  UserModel({
    required this.id,
    required this.name,
    required this.username,
    required this.role,
    this.roles = const <String>[],
    this.activeRole = '-',
  });

  final int id;
  final String name;
  final String username;
  final String role;
  final List<String> roles;
  final String activeRole;

  static const List<String> dashboardRolePriority = <String>[
    'teacher',
    'wali_asrama',
    'wali_murid',
    'majlis_participant',
  ];

  static const Map<String, String> roleLabels = <String, String>{
    'teacher': 'Guru',
    'wali_asrama': 'Wali Asrama',
    'wali_murid': 'Wali Murid',
    'majlis_participant': 'Peserta Majlis',
  };

  Set<String> get roleSet {
    return {
      if (role.trim().isNotEmpty && role.trim() != '-') _normalizeRole(role),
      ...roles
          .map(_normalizeRole)
          .where((item) => item.isNotEmpty && item != '-'),
    };
  }

  String get activeRoleKey {
    final normalized = _normalizeRole(activeRole);
    if (roleSet.contains(normalized)) {
      return normalized;
    }
    return defaultDashboardRole ?? normalized;
  }

  String get activeRoleLabel {
    return roleLabels[activeRoleKey] ?? activeRoleKey.replaceAll('_', ' ');
  }

  List<String> get dashboardRoles {
    final available = roleSet;
    return dashboardRolePriority
        .where((role) => available.contains(role))
        .toList();
  }

  String? get defaultDashboardRole {
    final dashboards = dashboardRoles;
    return dashboards.isNotEmpty ? dashboards.first : null;
  }

  bool hasRole(String value) {
    return roleSet.contains(_normalizeRole(value));
  }

  UserModel withActiveRole(String value) {
    final normalized = _normalizeRole(value);
    return UserModel(
      id: id,
      name: name,
      username: username,
      role: role,
      roles: roles,
      activeRole: roleSet.contains(normalized)
          ? normalized
          : (defaultDashboardRole ?? activeRole),
    );
  }

  bool get isParent {
    return roleSet.any(
      (item) => item.contains('wali_murid') || item.contains('parent'),
    );
  }

  bool get isMajlisParticipant {
    return roleSet.any((item) => item.contains('majlis'));
  }

  bool get isTeacher {
    return roleSet.any(
      (item) => item.contains('guru') || item.contains('teacher'),
    );
  }

  bool get isBoardingGuardian {
    return roleSet.any(
      (item) =>
          item.contains('wali_asrama') ||
          item.contains('boarding_guardian') ||
          item.contains('asrama'),
    );
  }

  factory UserModel.fromJson(Map<String, dynamic> json) {
    final parsedRoles = JsonHelper.asList(json['roles'])
        .map((item) => JsonHelper.asString(item))
        .where((item) => item.isNotEmpty)
        .toList();
    final activeRole = JsonHelper.asString(
      json['active_role'],
      fallback: JsonHelper.asString(json['role']),
    );
    final fallbackRole = activeRole.isNotEmpty
        ? activeRole
        : (parsedRoles.isNotEmpty ? parsedRoles.first : '-');

    return UserModel(
      id: JsonHelper.asInt(json['id']),
      name: JsonHelper.asString(
        json['name'] ?? json['full_name'] ?? json['fullName'],
        fallback: '-',
      ),
      username: JsonHelper.asString(
        json['username'] ?? json['phone'] ?? json['email'],
        fallback: '-',
      ),
      role: fallbackRole,
      roles: parsedRoles,
      activeRole: activeRole,
    );
  }

  static String _normalizeRole(String value) {
    final normalized = value.trim().toLowerCase();
    if (normalized == 'guru') return 'teacher';
    if (normalized == 'parent') return 'wali_murid';
    if (normalized == 'boarding_guardian') return 'wali_asrama';
    return normalized;
  }
}
