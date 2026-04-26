import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import 'app_button.dart';
import 'app_card.dart';

class AppErrorState extends StatelessWidget {
  const AppErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.error_outline_rounded, color: AppColors.danger),
              SizedBox(width: 8),
              Text(
                'Terjadi Kesalahan',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(message),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            AppButton(
              label: 'Coba Lagi',
              onPressed: onRetry,
              icon: Icons.refresh_rounded,
            ),
          ],
        ],
      ),
    );
  }
}
