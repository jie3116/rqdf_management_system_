import 'package:flutter/material.dart';

import '../../../../../core/utils/app_date_formatter.dart';
import '../../../../../core/theme/app_colors.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../../../../shared/widgets/app_empty_state.dart';
import '../../data/models/announcement_model.dart';

class AnnouncementsSection extends StatelessWidget {
  const AnnouncementsSection({
    super.key,
    required this.announcements,
    required this.unreadCount,
    this.maxItems,
  });

  final List<AnnouncementModel> announcements;
  final int unreadCount;
  final int? maxItems;

  @override
  Widget build(BuildContext context) {
    if (announcements.isEmpty) {
      return const AppEmptyState(
        title: 'Belum Ada Pengumuman',
        subtitle: 'Informasi terbaru sekolah akan tampil di sini.',
        icon: Icons.campaign_outlined,
      );
    }

    final visibleAnnouncements = maxItems == null
        ? announcements
        : announcements.take(maxItems!).toList();

    return Column(
      children: [
        if (unreadCount > 0)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFEFEF),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '$unreadCount belum dibaca',
                    style: const TextStyle(
                      color: Color(0xFFB91C1C),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ...visibleAnnouncements.map(
          (item) => Padding(
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
                      color: item.isUnread
                          ? const Color(0xFFFFEFEF)
                          : AppColors.accentBlueSoft,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      item.isUnread
                          ? Icons.notifications_active_outlined
                          : Icons.notifications_none_rounded,
                      color: item.isUnread
                          ? const Color(0xFFB91C1C)
                          : AppColors.accentBlue,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.title,
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 14.5,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${item.authorLabel} • ${AppDateFormatter.shortDate(item.createdAt)}',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12.5,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          item.content,
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            height: 1.45,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
