import 'package:flutter/material.dart';

import '../../../../../core/utils/app_date_formatter.dart';
import '../../../../../core/theme/app_colors.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../../../../shared/widgets/app_empty_state.dart';
import '../../data/models/recent_activity_model.dart';

class RecentActivitiesSection extends StatelessWidget {
  const RecentActivitiesSection({
    super.key,
    required this.activities,
    this.maxItems,
  });

  final List<RecentActivityModel> activities;
  final int? maxItems;

  @override
  Widget build(BuildContext context) {
    if (activities.isEmpty) {
      return const AppEmptyState(
        title: 'Belum Ada Aktivitas',
        subtitle: 'Aktivitas terbaru anak akan tampil di sini.',
        icon: Icons.event_busy_outlined,
      );
    }

    final visibleActivities =
        maxItems == null ? activities : activities.take(maxItems!).toList();

    return Column(
      children: visibleActivities.asMap().entries.map((entry) {
        final activity = entry.value;
        final color = _colorByType(activity.type);

        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: AppCard(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(
                    _iconByType(activity.type),
                    color: color,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _labelByType(activity.type),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: color,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        activity.message,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        AppDateFormatter.dateLabel(activity.createdAt),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                if (entry.key == 0)
                  const Padding(
                    padding: EdgeInsets.only(left: 8, top: 2),
                    child: Icon(
                      Icons.circle,
                      size: 10,
                      color: AppColors.accentBlue,
                    ),
                  ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  IconData _iconByType(String type) {
    switch (type.toLowerCase()) {
      case 'danger':
      case 'error':
        return Icons.error_outline_rounded;
      case 'warning':
        return Icons.warning_amber_rounded;
      case 'success':
        return Icons.check_circle_outline_rounded;
      default:
        return Icons.info_outline_rounded;
    }
  }

  Color _colorByType(String type) {
    switch (type.toLowerCase()) {
      case 'danger':
      case 'error':
        return AppColors.danger;
      case 'warning':
        return AppColors.warning;
      case 'success':
        return AppColors.success;
      default:
        return AppColors.accentBlue;
    }
  }

  String _labelByType(String type) {
    switch (type.toLowerCase()) {
      case 'danger':
      case 'error':
        return 'Perlu perhatian';
      case 'warning':
        return 'Pengingat';
      case 'success':
        return 'Update positif';
      default:
        return 'Info terbaru';
    }
  }
}
