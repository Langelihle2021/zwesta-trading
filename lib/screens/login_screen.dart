import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
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
        appBar: null,
        extendBodyBehindAppBar: true,
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF0052CC), Color(0xFF1E3A8A), Color(0xFF260B57)],
            ),
          ),
          child: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 20),
                  // Logo and Title
                  Center(
                    child: Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.15),
                          width: 2,
                        ),
                      ),
                      child: Column(
                        children: [
                          const LogoWidget(size: 120, showText: false),
                          const SizedBox(height: 16),
                          Text(
                            'ZWESTA XM',
                            style: GoogleFonts.poppins(
                              color: Colors.white,
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.2,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'TRADING SYSTEM',
                            style: GoogleFonts.poppins(
                              color: Colors.white70,
                              fontSize: 12,
                              letterSpacing: 2,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 60),
                  
                  // Welcome Back heading (only on login)
                  if (_isLogin && !_showMfaPrompt)
                    Text(
                      'Welcome Back',
                      style: GoogleFonts.poppins(
                        color: Colors.white,
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    )
                  else if (!_isLogin)
                    Text(
                      'Create Account',
                      style: GoogleFonts.poppins(
                        color: Colors.white,
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    )
                  else
                    Text(
                      'Two-Factor Authentication',
                      style: GoogleFonts.poppins(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  const SizedBox(height: 36),

                  // Success Message Display
                  Consumer<AuthService>(
                    builder: (context, authService, _) {
                      if (authService.successMessage != null && authService.successMessage!.isNotEmpty) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.green.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.green.withOpacity(0.5)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.check_circle_outline, color: Colors.greenAccent, size: 20),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    authService.successMessage!,
                                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                                  ),
                                ),
                                GestureDetector(
                                  onTap: () => authService.clearError(),
                                  child: const Icon(Icons.close, color: Colors.white70, size: 18),
                                ),
                              ],
                            ),
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    },
                  ),

                  // Error Message Display
                  Consumer<AuthService>(
                    builder: (context, authService, _) {
                      if (authService.errorMessage != null && authService.errorMessage!.isNotEmpty) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.red.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.red.withOpacity(0.5)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    authService.errorMessage!,
                                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                                  ),
                                ),
                                GestureDetector(
                                  onTap: () => authService.clearError(),
                                  child: const Icon(Icons.close, color: Colors.white70, size: 18),
                                ),
                              ],
                            ),
                          ),
                        );
                      }
                      return const SizedBox.shrink();
                    },
                  ),

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
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Enter the 2FA code sent to your email.',
          style: GoogleFonts.poppins(
            color: Colors.white70,
            fontSize: 15,
            height: 1.5,
          ),
        ),
        const SizedBox(height: 32),
        TextField(
          controller: _mfaController,
          keyboardType: TextInputType.number,
          maxLength: 6,
          style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, letterSpacing: 2),
          cursorColor: Colors.white,
          textAlign: TextAlign.center,
          decoration: InputDecoration(
            hintText: '000000',
            hintStyle: GoogleFonts.poppins(color: Colors.white30, fontSize: 18),
            filled: true,
            fillColor: Colors.white.withOpacity(0.1),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: Colors.white, width: 2),
            ),
            counterText: '',
            contentPadding: const EdgeInsets.symmetric(vertical: 16),
          ),
        ),
        const SizedBox(height: 32),
        Consumer<AuthService>(
          builder: (context, authService, _) {
            return SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0066FF),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  elevation: 4,
                ),
                onPressed: authService.isLoading ? null : _verifyMfaCode,
                child: authService.isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation(Colors.white),
                        ),
                      )
                    : Text(
                        'Verify Code',
                        style: GoogleFonts.poppins(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            );
          },
        ),
        const SizedBox(height: 16),
        Center(
          child: TextButton(
            onPressed: _resendMfaCode,
            child: Text(
              'Resend Code',
              style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14),
            ),
          ),
        ),
      ],
    );
  }

  // Build login/register form
  Widget _buildLoginRegisterForm(AppLocalizations loc) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!_isLogin) ...[
          // Registration fields
          TextField(
            controller: _firstNameController,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 15),
            cursorColor: Colors.white,
            decoration: InputDecoration(
              hintText: 'First Name',
              hintStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 15),
              prefixIcon: const Icon(Icons.person, color: Colors.white70, size: 20),
              filled: true,
              fillColor: Colors.white.withOpacity(0.08),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: Colors.white, width: 2),
              ),
              contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _lastNameController,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 15),
            cursorColor: Colors.white,
            decoration: InputDecoration(
              hintText: 'Last Name',
              hintStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 15),
              prefixIcon: const Icon(Icons.person, color: Colors.white70, size: 20),
              filled: true,
              fillColor: Colors.white.withOpacity(0.08),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: Colors.white, width: 2),
              ),
              contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _emailController,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 15),
            cursorColor: Colors.white,
            decoration: InputDecoration(
              hintText: 'Email',
              hintStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 15),
              prefixIcon: const Icon(Icons.email, color: Colors.white70, size: 20),
              filled: true,
              fillColor: Colors.white.withOpacity(0.08),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: Colors.white, width: 2),
              ),
              contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Username field
        TextField(
          controller: _usernameController,
          style: GoogleFonts.poppins(color: Colors.white, fontSize: 15),
          cursorColor: Colors.white,
          decoration: InputDecoration(
            hintText: 'Username',
            hintStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 15),
            prefixIcon: const Icon(Icons.person, color: Colors.white70, size: 20),
            filled: true,
            fillColor: Colors.white.withOpacity(0.08),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: Colors.white, width: 2),
            ),
            contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
          ),
        ),
        const SizedBox(height: 16),

        // Password field
        TextField(
          controller: _passwordController,
          style: GoogleFonts.poppins(color: Colors.white, fontSize: 15),
          cursorColor: Colors.white,
          obscureText: _obscurePassword,
          decoration: InputDecoration(
            hintText: 'Password',
            hintStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 15),
            prefixIcon: const Icon(Icons.lock, color: Colors.white70, size: 20),
            suffixIcon: GestureDetector(
              onTap: () {
                setState(() => _obscurePassword = !_obscurePassword);
              },
              child: Icon(
                _obscurePassword ? Icons.visibility_off : Icons.visibility,
                color: Colors.white70,
                size: 20,
              ),
            ),
            filled: true,
            fillColor: Colors.white.withOpacity(0.08),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: BorderSide(color: Colors.white.withOpacity(0.2), width: 1.5),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: Colors.white, width: 2),
            ),
            contentPadding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
          ),
        ),
        const SizedBox(height: 40),

        // Submit Button
        Consumer<AuthService>(
          builder: (context, authService, _) {
            return SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0066FF),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  elevation: 4,
                ),
                onPressed: authService.isLoading ? null : _handleSubmit,
                child: authService.isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation(Colors.white),
                        ),
                      )
                    : Text(
                        _isLogin ? 'Login' : 'Create Account',
                        style: GoogleFonts.poppins(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            );
          },
        ),
        const SizedBox(height: 28),

        // Toggle login/register
        Center(
          child: RichText(
            text: TextSpan(
              children: [
                TextSpan(
                  text: _isLogin ? "Don't have an account? " : "Already have an account? ",
                  style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14),
                ),
                TextSpan(
                  text: _isLogin ? 'Register' : 'Login',
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    decoration: TextDecoration.underline,
                  ),
                  recognizer: TapGestureRecognizer()
                    ..onTap = () {
                      setState(() => _isLogin = !_isLogin);
                    },
                ),
              ],
            ),
          ),
        ),

        // Forgot password
        if (_isLogin)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Center(
              child: GestureDetector(
                onTap: () {
                  setState(() => _showForgotPassword = true);
                },
                child: Text(
                  'Forgot Password?',
                  style: GoogleFonts.poppins(
                    color: Colors.white70,
                    fontSize: 12,
                    decoration: TextDecoration.underline,
                  ),
                ),
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
