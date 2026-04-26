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

  List<String> get _rolePool {
    final values = <String>{
      if (role.trim().isNotEmpty && role.trim() != '-')
        role.trim().toLowerCase(),
      if (activeRole.trim().isNotEmpty && activeRole.trim() != '-')
        activeRole.trim().toLowerCase(),
      ...roles
          .map((item) => item.trim().toLowerCase())
          .where((item) => item.isNotEmpty && item != '-'),
    };
    return values.toList();
  }

  bool get isParent {
    return _rolePool.any(
      (item) => item.contains('wali_murid') || item.contains('parent'),
    );
  }

  bool get isMajlisParticipant {
    return _rolePool.any((item) => item.contains('majlis'));
  }

  bool get isTeacher {
    return _rolePool.any(
      (item) => item.contains('guru') || item.contains('teacher'),
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
}
