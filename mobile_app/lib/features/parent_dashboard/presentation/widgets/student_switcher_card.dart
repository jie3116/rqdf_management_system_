import 'package:flutter/material.dart';

import '../../../../../core/theme/app_colors.dart';
import '../../../../../shared/widgets/app_card.dart';
import '../../data/models/child_model.dart';

class StudentSwitcherCard extends StatelessWidget {
  const StudentSwitcherCard({
    super.key,
    required this.selectedChild,
    required this.children,
    required this.onChanged,
  });

  final ChildModel? selectedChild;
  final List<ChildModel> children;
  final ValueChanged<ChildModel> onChanged;

  @override
  Widget build(BuildContext context) {
    if (selectedChild == null) {
      return const AppCard(child: Text('Belum ada data anak aktif.'));
    }

    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: () => _showChildPicker(context),
      child: AppCard(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFFEAF3FF), Color(0xFFD8E8FF)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Center(
                child: Text(
                  selectedChild!.name.isNotEmpty
                      ? selectedChild!.name[0].toUpperCase()
                      : 'A',
                  style: const TextStyle(
                    fontWeight: FontWeight.w800,
                    color: AppColors.primary,
                    fontSize: 18,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Anak aktif',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppColors.textSecondary,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    selectedChild!.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    selectedChild!.className,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.accentBlueSoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.keyboard_arrow_down_rounded,
                color: AppColors.accentBlue,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showChildPicker(BuildContext context) async {
    if (children.isEmpty) return;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            shrinkWrap: true,
            itemBuilder: (_, index) {
              final child = children[index];
              return ListTile(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
                tileColor: child.id == selectedChild?.id
                    ? AppColors.accentBlueSoft
                    : Colors.transparent,
                leading: CircleAvatar(
                  backgroundColor: const Color(0xFFEAF3FF),
                  child: Text(
                    child.name.isNotEmpty ? child.name[0] : 'A',
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                title: Text(child.name),
                subtitle: Text(child.className),
                trailing: child.id == selectedChild?.id
                    ? const Icon(Icons.check_circle, color: AppColors.accentBlue)
                    : null,
                onTap: () {
                  onChanged(child);
                  Navigator.of(context).pop();
                },
              );
            },
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemCount: children.length,
          ),
        );
      },
    );
  }
}
