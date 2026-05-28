import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../data/models/user_model.dart';
import '../providers/auth_provider.dart';
import '../utils/auth_navigation.dart';

class RoleSwitcherButton extends StatelessWidget {
  const RoleSwitcherButton({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final roles = user?.dashboardRoles ?? const <String>[];
    if (user == null || roles.length <= 1) {
      return const SizedBox.shrink();
    }

    return PopupMenuButton<String>(
      tooltip: 'Ganti role',
      icon: const Icon(Icons.switch_account_outlined),
      initialValue: user.activeRoleKey,
      onSelected: (role) => _switchRole(context, role),
      itemBuilder: (context) {
        return roles.map((role) {
          final selected = role == user.activeRoleKey;
          return PopupMenuItem<String>(
            value: role,
            child: Row(
              children: [
                Icon(
                  selected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  size: 18,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    UserModel.roleLabels[role] ?? role.replaceAll('_', ' '),
                  ),
                ),
              ],
            ),
          );
        }).toList();
      },
    );
  }

  Future<void> _switchRole(BuildContext context, String role) async {
    final authProvider = context.read<AuthProvider>();
    await authProvider.switchActiveRole(role);
    if (!context.mounted) return;

    final route = AuthNavigation.routeForUser(authProvider.currentUser);
    Navigator.of(context).pushNamedAndRemoveUntil(route, (_) => false);
  }
}
