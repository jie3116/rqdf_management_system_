import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../shared/models/view_state.dart';
import '../../../majlis_dashboard/presentation/providers/majlis_dashboard_provider.dart';
import '../../../parent_dashboard/presentation/providers/dashboard_provider.dart';
import '../../../teacher_dashboard/presentation/providers/teacher_dashboard_provider.dart';
import '../providers/auth_provider.dart';
import '../utils/auth_navigation.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  static const String routeName = '/login';

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _identifierController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
  String? _localError;

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;

    setState(() => _localError = null);

    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.login(
      identifier: _identifierController.text.trim(),
      password: _passwordController.text,
      rememberMeChoice: false,
    );

    if (!mounted || !success) return;

    final user = authProvider.currentUser;
    final nextRoute = AuthNavigation.routeForUser(user);

    if (user?.isTeacher == true) {
      await context
          .read<TeacherDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
    } else if (user?.isMajlisParticipant == true) {
      await context
          .read<MajlisDashboardProvider>()
          .fetchDashboard(forceRefresh: true);
    } else {
      await context
          .read<DashboardProvider>()
          .fetchDashboard(forceRefresh: true);
    }
    if (!mounted) return;
    Navigator.of(context).pushReplacementNamed(nextRoute);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final authProvider = context.watch<AuthProvider>();
    final isLoading = authProvider.state == ViewState.loading;
    final errorText = _localError ?? authProvider.errorMessage;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFF102B52),
              Color(0xFF143A6F),
              Color(0xFF2F80ED),
            ],
          ),
        ),
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _PatternPainter(),
              ),
            ),
            const Positioned(
              top: -70,
              right: -20,
              child: _GlowCircle(
                size: 190,
                colors: [Color(0x20FFFFFF), Color(0x00FFFFFF)],
              ),
            ),
            const Positioned(
              bottom: -90,
              left: -30,
              child: _GlowCircle(
                size: 240,
                colors: [Color(0x2038BDF8), Color(0x0038BDF8)],
              ),
            ),
            SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: Column(
                      children: [
                        Container(
                          width: 132,
                          height: 132,
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(36),
                            border: Border.all(
                              color: Colors.white.withValues(alpha: 0.14),
                            ),
                          ),
                          child: Image.asset(
                            'assets/images/logo-rqdf-white.png',
                            fit: BoxFit.contain,
                          ),
                        ),
                        const SizedBox(height: 18),
                        RichText(
                          textAlign: TextAlign.center,
                          text: TextSpan(
                            children: [
                              TextSpan(
                                text: 'RQDF',
                                style: theme.textTheme.headlineMedium?.copyWith(
                                  color: Colors.white,
                                  fontSize: 34,
                                  fontWeight: FontWeight.w900,
                                  fontStyle: FontStyle.italic,
                                  letterSpacing: 0.5,
                                  height: 0.95,
                                ),
                              ),
                              TextSpan(
                                text: ' Mobile',
                                style: theme.textTheme.titleMedium?.copyWith(
                                  color: const Color(0xFFDCEAFF),
                                  fontSize: 17,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: 0.8,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        Container(
                          padding: const EdgeInsets.all(22),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(28),
                            boxShadow: const [
                              BoxShadow(
                                color: Color(0x1A0F172A),
                                blurRadius: 28,
                                offset: Offset(0, 12),
                              ),
                            ],
                          ),
                          child: Form(
                            key: _formKey,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Silahkan Login',
                                  style:
                                      theme.textTheme.headlineSmall?.copyWith(
                                    color: AppColors.textPrimary,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 18),
                                TextFormField(
                                  controller: _identifierController,
                                  textInputAction: TextInputAction.next,
                                  decoration: InputDecoration(
                                    hintText: 'Username / Email / No. HP',
                                    hintStyle: const TextStyle(
                                      color: Color(0xFF64748B),
                                      fontWeight: FontWeight.w500,
                                    ),
                                    prefixIcon: const Icon(
                                      Icons.person_outline_rounded,
                                      color: AppColors.accentBlue,
                                    ),
                                    fillColor: const Color(0xFFF7FAFF),
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(18),
                                    ),
                                  ),
                                  validator: (value) {
                                    if (value == null || value.trim().isEmpty) {
                                      return 'Masukkan username atau email.';
                                    }
                                    return null;
                                  },
                                ),
                                const SizedBox(height: 14),
                                TextFormField(
                                  controller: _passwordController,
                                  textInputAction: TextInputAction.done,
                                  obscureText: _obscurePassword,
                                  onFieldSubmitted: (_) => _submit(),
                                  decoration: InputDecoration(
                                    hintText: 'Password',
                                    hintStyle: const TextStyle(
                                      color: Color(0xFF64748B),
                                      fontWeight: FontWeight.w500,
                                    ),
                                    prefixIcon: const Icon(
                                      Icons.lock_outline_rounded,
                                      color: AppColors.accentBlue,
                                    ),
                                    suffixIcon: IconButton(
                                      onPressed: () {
                                        setState(() {
                                          _obscurePassword = !_obscurePassword;
                                        });
                                      },
                                      icon: Icon(
                                        _obscurePassword
                                            ? Icons.visibility_off_outlined
                                            : Icons.visibility_outlined,
                                        color: const Color(0xFF64748B),
                                      ),
                                    ),
                                    fillColor: const Color(0xFFF7FAFF),
                                    border: OutlineInputBorder(
                                      borderRadius: BorderRadius.circular(18),
                                    ),
                                  ),
                                  validator: (value) {
                                    if (value == null || value.isEmpty) {
                                      return 'Masukkan password.';
                                    }
                                    return null;
                                  },
                                ),
                                if (errorText != null &&
                                    errorText.trim().isNotEmpty) ...[
                                  const SizedBox(height: 14),
                                  Container(
                                    width: double.infinity,
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFFFF1F2),
                                      borderRadius: BorderRadius.circular(16),
                                      border: Border.all(
                                        color: const Color(0xFFFECDD3),
                                      ),
                                    ),
                                    child: Text(
                                      errorText,
                                      style: const TextStyle(
                                        color: AppColors.danger,
                                        fontWeight: FontWeight.w600,
                                        height: 1.35,
                                      ),
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 18),
                                SizedBox(
                                  width: double.infinity,
                                  height: 56,
                                  child: FilledButton(
                                    onPressed: isLoading ? null : _submit,
                                    style: FilledButton.styleFrom(
                                      backgroundColor: const Color(0xFF2563EB),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(18),
                                      ),
                                    ),
                                    child: isLoading
                                        ? const SizedBox(
                                            width: 22,
                                            height: 22,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2.4,
                                              color: Colors.white,
                                            ),
                                          )
                                        : const Text(
                                            'Masuk',
                                            style: TextStyle(
                                              fontSize: 16.5,
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GlowCircle extends StatelessWidget {
  const _GlowCircle({
    required this.size,
    required this.colors,
  });

  final double size;
  final List<Color> colors;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(colors: colors),
        ),
      ),
    );
  }
}

class _PatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final dotPaint = Paint()..color = Colors.white.withValues(alpha: 0.04);
    const spacing = 26.0;
    const radius = 1.2;

    for (double y = 12; y < size.height; y += spacing) {
      for (double x = 12; x < size.width; x += spacing) {
        canvas.drawCircle(Offset(x, y), radius, dotPaint);
      }
    }

    final linePaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.035)
      ..strokeWidth = 1;
    final path = Path()
      ..moveTo(size.width * 0.08, size.height * 0.22)
      ..quadraticBezierTo(
        size.width * 0.28,
        size.height * 0.16,
        size.width * 0.52,
        size.height * 0.24,
      )
      ..quadraticBezierTo(
        size.width * 0.78,
        size.height * 0.32,
        size.width * 0.94,
        size.height * 0.24,
      );
    canvas.drawPath(path, linePaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
