import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../widgets/custom_widgets.dart';
import 'package:provider/provider.dart';
import '../widgets/logo_widget.dart';
import '../l10n/app_localizations.dart';
import 'forgot_password_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late TextEditingController _usernameController;
  late TextEditingController _passwordController;
  late TextEditingController _mfaController;
  bool _obscurePassword = true;
  bool _isLogin = true;
  bool _showForgotPassword = false;
  bool _showMfaPrompt = false;
  String? _pendingSessionToken;
  late TextEditingController _emailController;
  late TextEditingController _firstNameController;
  late TextEditingController _lastNameController;

  @override
  void initState() {
    super.initState();
    _usernameController = TextEditingController();
    _passwordController = TextEditingController();
    _mfaController = TextEditingController();
    _emailController = TextEditingController();
    _firstNameController = TextEditingController();
    _lastNameController = TextEditingController();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _mfaController.dispose();
    _emailController.dispose();
    _firstNameController.dispose();
    _lastNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Show forgot password screen
    if (_showForgotPassword) {
      return ForgotPasswordScreen(
        onBackToLogin: () {
          setState(() => _showForgotPassword = false);
        },
      );
    }

    final loc = AppLocalizations.of(context)!;
    try {
      return Scaffold(
        appBar: CustomAppBar(
          title: _isLogin ? loc.translate('welcome', params: {'name': ''}) : loc.translate('Create Your Account'),
          showBackButton: false,
        ),
        extendBodyBehindAppBar: true,
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF0A0E21), Color(0xFF1A237E), Color(0xFF512DA8)],
            ),
          ),
          child: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Card(
                  elevation: 8,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  color: Colors.white.withOpacity(0.04),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Logo Header
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.08),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: Colors.white.withOpacity(0.15),
                              width: 1.5,
                            ),
                          ),
                          child: const LogoWidget(size: 100, showText: true),
                        ),
                        const SizedBox(height: AppSpacing.lg),
                        // Error Message Display
                        Consumer<AuthService>(
                          builder: (context, authService, _) {
                            if (authService.errorMessage != null && authService.errorMessage!.isNotEmpty) {
                              return ErrorBanner(
                                message: authService.errorMessage!,
                                onDismiss: () => authService.clearError(),
                              );
                            }
                            return const SizedBox.shrink();
                          },
                        ),
                        const SizedBox(height: AppSpacing.md),
                        // Show MFA prompt or login/register form
                        if (_showMfaPrompt)
                          _buildMfaForm(loc)
                        else
                          _buildLoginRegisterForm(loc),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    } catch (e, st) {
      print('LoginScreen build error: $e\n$st');
      return Scaffold(
        body: Center(child: Text('Login error: $e')),
      );
    }
  }

  // Build MFA/2FA form
  Widget _buildMfaForm(AppLocalizations loc) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Two-Factor Authentication',
          style: GoogleFonts.poppins(
            color: Colors.white,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'Enter the 2FA code sent to your email.',
          style: GoogleFonts.roboto(
            color: Colors.white70,
            fontSize: 14,
          ),
        ),
        const SizedBox(height: 24),
        TextField(
          controller: _mfaController,
          keyboardType: TextInputType.number,
          maxLength: 6,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '2FA Code',
            hintStyle: const TextStyle(color: Colors.white54),
            prefixIcon: const Icon(Icons.password, color: Colors.white70),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white),
            ),
          ),
        ),
        const SizedBox(height: 24),
        Consumer<AuthService>(
          builder: (context, authService, _) {
            return SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.blue[900],
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: authService.isLoading ? null : _verifyMfaCode,
                child: authService.isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        'Verify Code',
                        style: GoogleFonts.poppins(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            );
          },
        ),
        const SizedBox(height: 12),
        Center(
          child: TextButton(
            onPressed: _resendMfaCode,
            child: const Text('Resend Code', style: TextStyle(color: Colors.white70)),
          ),
        ),
      ],
    );
  }

  // Build login/register form
  Widget _buildLoginRegisterForm(AppLocalizations loc) {
    return Column(
      children: [
        if (!_isLogin) ...[
          // Registration fields
          TextFormField(
            controller: _firstNameController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: loc.translate('First Name'),
              hintStyle: const TextStyle(color: Colors.white54),
              prefixIcon: const Icon(Icons.person, color: Colors.white70),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          TextFormField(
            controller: _lastNameController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: loc.translate('Last Name'),
              hintStyle: const TextStyle(color: Colors.white54),
              prefixIcon: const Icon(Icons.person, color: Colors.white70),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          TextFormField(
            controller: _emailController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: loc.translate('Email'),
              hintStyle: const TextStyle(color: Colors.white54),
              prefixIcon: const Icon(Icons.email, color: Colors.white70),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Colors.white30),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],

        // Username field
        TextFormField(
          controller: _usernameController,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: loc.translate('Email'),
            hintStyle: const TextStyle(color: Colors.white54),
            prefixIcon: const Icon(Icons.person, color: Colors.white70),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Password field
        TextFormField(
          controller: _passwordController,
          style: const TextStyle(color: Colors.white),
          obscureText: _obscurePassword,
          decoration: InputDecoration(
            hintText: loc.translate('Password'),
            hintStyle: const TextStyle(color: Colors.white54),
            prefixIcon: const Icon(Icons.lock, color: Colors.white70),
            suffixIcon: GestureDetector(
              onTap: () {
                setState(() => _obscurePassword = !_obscurePassword);
              },
              child: Icon(
                _obscurePassword ? Icons.visibility : Icons.visibility_off,
                color: Colors.white70,
              ),
            ),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.white30),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),

        // Submit Button
        Consumer<AuthService>(
          builder: (context, authService, _) {
            return SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.blue[900],
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: authService.isLoading ? null : _handleSubmit,
                child: authService.isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(
                        _isLogin ? loc.translate('Sign In') : loc.translate('Create Account'),
                        style: GoogleFonts.poppins(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            );
          },
        ),
        const SizedBox(height: AppSpacing.md),

        // Toggle login/register
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              _isLogin ? "Don't have an account? " : "Already have an account? ",
              style: const TextStyle(color: Colors.white70),
            ),
            GestureDetector(
              onTap: () {
                setState(() => _isLogin = !_isLogin);
              },
              child: Text(
                _isLogin ? 'Sign Up' : 'Sign In',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),

        // Forgot password
        if (_isLogin)
          GestureDetector(
            onTap: () {
              setState(() => _showForgotPassword = true);
            },
            child: Text(
              'Forgot Password?',
              style: GoogleFonts.roboto(
                color: Colors.white70,
                fontSize: 12,
                decoration: TextDecoration.underline,
              ),
            ),
          ),
      ],
    );
  }

  // Handle login/register submission
  void _handleSubmit() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    
    if (_isLogin) {
      final success = await authService.login(
        _usernameController.text.trim(),
        _passwordController.text,
      );
      if (success && mounted) {
        // Check if 2FA is required
        if (_showMfaPrompt) {
          setState(() => _showMfaPrompt = true);
        }
      }
    } else {
      final success = await authService.register(
        _usernameController.text.trim(),
        _emailController.text.trim(),
        _passwordController.text,
        _firstNameController.text.trim(),
        _lastNameController.text.trim(),
      );
      if (success && mounted) {
        setState(() => _isLogin = true);
      }
    }
  }

  // Verify 2FA/MFA code
  void _verifyMfaCode() async {
    final code = _mfaController.text.trim();
    if (code.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter the 2FA code')),
      );
      return;
    }

    final authService = Provider.of<AuthService>(context, listen: false);
    final success = await authService.verifyMfaCode(_pendingSessionToken, code);
    
    if (success && mounted) {
      setState(() {
        _showMfaPrompt = false;
        _mfaController.clear();
        _pendingSessionToken = null;
      });
    }
  }

  // Resend 2FA code
  void _resendMfaCode() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    await authService.resendMfaCode(_pendingSessionToken);
    
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('2FA code resent to your email')),
      );
    }
  }
}
