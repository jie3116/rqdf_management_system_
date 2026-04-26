import 'package:flutter/material.dart';

import '../../../../../core/theme/app_colors.dart';
import '../../data/models/quick_action_model.dart';

class QuickActionGrid extends StatelessWidget {
  const QuickActionGrid({
    super.key,
    required this.actions,
    required this.onTapAction,
  });

  final List<QuickActionModel> actions;
  final ValueChanged<QuickActionModel> onTapAction;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      itemCount: actions.length,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisExtent: 98,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (_, index) {
        final item = actions[index];
        final tint = _colorFor(item.key);

        return InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => onTapAction(item),
          child: Ink(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.borderSoft),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x0C0F172A),
                  blurRadius: 18,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: tint.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(_iconFor(item.key), size: 22, color: tint),
                ),
                const SizedBox(height: 8),
                Text(
                  item.label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  IconData _iconFor(String key) {
    switch (key.toLowerCase()) {
      case 'pengumuman':
        return Icons.campaign_rounded;
      case 'keuangan':
        return Icons.account_balance_wallet_outlined;
      case 'tahfidz':
        return Icons.menu_book_outlined;
      case 'jadwal':
        return Icons.event_note_outlined;
      case 'nilai':
        return Icons.bar_chart_rounded;
      case 'absensi':
        return Icons.fact_check_outlined;
      case 'evaluasi':
        return Icons.assignment_turned_in_outlined;
      case 'profil':
        return Icons.person_outline_rounded;
      case 'perilaku':
        return Icons.emoji_people_outlined;
      default:
        return Icons.apps_rounded;
    }
  }

  Color _colorFor(String key) {
    switch (key.toLowerCase()) {
      case 'pengumuman':
        return const Color(0xFFEF4444);
      case 'keuangan':
        return const Color(0xFFF59E0B);
      case 'tahfidz':
        return AppColors.success;
      case 'jadwal':
        return const Color(0xFF7C3AED);
      case 'nilai':
        return AppColors.accentBlue;
      case 'absensi':
        return AppColors.accentTeal;
      case 'evaluasi':
        return const Color(0xFF6366F1);
      case 'profil':
        return const Color(0xFF0EA5A4);
      case 'perilaku':
        return AppColors.danger;
      default:
        return AppColors.primary;
    }
  }
}
