import 'package:flutter/material.dart';

class FeaturePlaceholderScreen extends StatelessWidget {
  const FeaturePlaceholderScreen({
    super.key,
    required this.title,
  });

  static const String routeName = '/feature-placeholder';
  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Text(
            '$title sedang disiapkan. Struktur routing sudah siap untuk integrasi halaman ini.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
