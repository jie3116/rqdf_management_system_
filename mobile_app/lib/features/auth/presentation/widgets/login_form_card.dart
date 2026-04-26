import 'package:flutter/material.dart';

import '../../../../../core/theme/app_colors.dart';

class LoginFormCard extends StatelessWidget {
  const LoginFormCard({
    super.key,
    required this.identifierController,
    required this.passwordController,
    required this.obscurePassword,
    required this.onToggleObscure,
    required this.onSubmit,
    required this.loading,
    this.errorMessage,
  });

  final TextEditingController identifierController;
  final TextEditingController passwordController;
  final bool obscurePassword;
  final VoidCallback onToggleObscure;
  final VoidCallback onSubmit;
  final bool loading;
  final String? errorMessage;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Silahkan Login',
          style: TextStyle(
            color: Colors.white,
            fontSize: 24,
            fontWeight: FontWeight.w800,
            height: 1.05,
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: identifierController,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(
            hintText: 'Username / Email / No. HP',
            hintStyle: TextStyle(
              fontSize: 12.8,
              color: Colors.white.withValues(alpha: 0.62),
              fontWeight: FontWeight.w400,
            ),
            prefixIcon: const Icon(
              Icons.person_outline_rounded,
              size: 18,
              color: Color(0xFFCCE0FF),
            ),
            fillColor: const Color(0x18FFFFFF),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: Color(0x2EFFFFFF)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide:
                  const BorderSide(color: Color(0x73FFFFFF), width: 1.2),
            ),
          ),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13.8,
            fontWeight: FontWeight.w500,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: passwordController,
          textInputAction: TextInputAction.done,
          obscureText: obscurePassword,
          onSubmitted: (_) => onSubmit(),
          decoration: InputDecoration(
            hintText: 'Password',
            hintStyle: TextStyle(
              fontSize: 12.8,
              color: Colors.white.withValues(alpha: 0.62),
              fontWeight: FontWeight.w400,
            ),
            prefixIcon: const Icon(
              Icons.lock_outline_rounded,
              size: 18,
              color: Color(0xFFCCE0FF),
            ),
            fillColor: const Color(0x18FFFFFF),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: Color(0x2EFFFFFF)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide:
                  const BorderSide(color: Color(0x73FFFFFF), width: 1.2),
            ),
            suffixIcon: IconButton(
              onPressed: onToggleObscure,
              icon: Icon(
                obscurePassword
                    ? Icons.visibility_off_outlined
                    : Icons.visibility_outlined,
                size: 20,
                color: const Color(0xFFD9E8FF),
              ),
            ),
          ),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13.8,
            fontWeight: FontWeight.w500,
          ),
        ),
        if (errorMessage != null && errorMessage!.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0x29DC2626),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0x55FCA5A5)),
            ),
            child: Text(
              errorMessage!,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w500,
                height: 1.4,
              ),
            ),
          ),
        ],
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: loading ? null : onSubmit,
            style: FilledButton.styleFrom(
              backgroundColor: Colors.white,
              disabledBackgroundColor: Colors.white54,
              foregroundColor: Colors.white,
              elevation: 0,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.primary,
                    ),
                  )
                : const Text(
                    'Login',
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.2,
                      color: AppColors.primary,
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}
