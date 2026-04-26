import 'package:flutter/material.dart';

import '../../../../../core/theme/app_colors.dart';
import '../../../../../core/utils/currency_formatter.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../data/models/dashboard_summary_model.dart';

class SummaryCard extends StatelessWidget {
  const SummaryCard({
    super.key,
    required this.summary,
  });

  final DashboardSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Ringkasan utama',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppColors.accentBlueSoft,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Text(
                  'Live',
                  style: TextStyle(
                    color: AppColors.accentBlue,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Pantauan cepat untuk kegiatan akademik, tahfidz, tagihan, perilaku, dll.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.45,
                ),
          ),
          const SizedBox(height: 12),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.45,
            children: [
              _MetricTile(
                label: 'Tagihan',
                value: CurrencyFormatter.rupiah(summary.billingTotal),
                icon: Icons.account_balance_wallet_rounded,
                accent: const Color(0xFFB45309),
                background: const Color(0xFFFFF6E8),
              ),
              _MetricTile(
                label: 'Pelanggaran',
                value: '${summary.violationPoints}',
                icon: Icons.gpp_maybe_rounded,
                accent: const Color(0xFFB91C1C),
                background: const Color(0xFFFFEEEE),
              ),
              _MetricTile(
                label: 'Tahfidz',
                value: summary.memorizationProgress,
                icon: Icons.menu_book_rounded,
                accent: const Color(0xFF047857),
                background: const Color(0xFFECFDF5),
              ),
              _MetricTile(
                label: 'Absensi',
                value: summary.attendanceStatus,
                icon: Icons.fact_check_rounded,
                accent: AppColors.accentBlue,
                background: AppColors.accentBlueSoft,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.accent,
    required this.background,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color accent;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.72),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 18, color: accent),
          ),
          const Spacer(),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.textSecondary,
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF0F172A),
                ),
          ),
        ],
      ),
    );
  }
}
