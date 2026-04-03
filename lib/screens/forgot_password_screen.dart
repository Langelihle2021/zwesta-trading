import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/password_reset_service.dart';

class ForgotPasswordScreen extends StatefulWidget {

  const ForgotPasswordScreen({
    required this.onBackToLogin, Key? key,
  }) : super(key: key);
  final VoidCallback onBackToLogin;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  late PasswordResetService _resetService;
  final _emailController = TextEditingController();
  final _otpController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  int _currentStep = 0; // 0: Email, 1: OTP, 2: New Password
  String _resetMethod = 'email'; // email or whatsapp

  @override
  void initState() {
    super.initState();
    _resetService = PasswordResetService();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _otpController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  // Step 1: Request OTP
  void _requestOtp() async {
    if (_emailController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter your email')),
      );
      return;
    }

    final success = await _resetService.requestPasswordReset(
      email: _emailController.text,
      method: _resetMethod,
    );

    if (success) {
      setState(() => _currentStep = 1);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_resetService.errorMessage ?? 'Error')),
      );
    }
  }

  // Step 2: Verify OTP
  void _verifyOtp() async {
    if (_otpController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter the OTP')),
      );
      return;
    }

    final success = await _resetService.verifyOtp(otp: _otpController.text);

    if (success) {
      setState(() => _currentStep = 2);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_resetService.errorMessage ?? 'Invalid OTP')),
      );
    }
  }

  // Step 3: Reset Password
  void _resetPassword() async {
    if (_passwordController.text.isEmpty ||
        _confirmPasswordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter password')),
      );
      return;
    }

    if (_passwordController.text != _confirmPasswordController.text) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Passwords do not match')),
      );
      return;
    }

    final success =
        await _resetService.resetPassword(newPassword: _passwordController.text);

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Password reset successfully')),
      );
      widget.onBackToLogin();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_resetService.errorMessage ?? 'Error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Colors.blue[900]!,
              Colors.blue[700]!,
              Colors.purple[400]!,
            ],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Back Button
                GestureDetector(
                  onTap: () {
                    if (_currentStep == 0) {
                      widget.onBackToLogin();
                    } else {
                      setState(() => _currentStep--);
                      _resetService.cancelReset();
                    }
                  },
                  child: Row(
                    children: [
                      const Icon(Icons.arrow_back, color: Colors.white),
                      const SizedBox(width: 8),
                      Text(
                        'Back',
                        style: GoogleFonts.poppins(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 40),

                // Title
                Text(
                  _currentStep == 0
                      ? 'Reset Password'
                      : _currentStep == 1
                          ? 'Verify OTP'
                          : 'New Password',
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),

                // Subtitle
                Text(
                  _currentStep == 0
                      ? 'Enter your email to receive an OTP'
                      : _currentStep == 1
                          ? 'Enter the code we sent to you'
                          : 'Create a new secure password',
                  style: GoogleFonts.roboto(
                    color: Colors.white70,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 40),

                // Step content
                if (_currentStep == 0) ...[
                  // Email Input
                  TextField(
                    controller: _emailController,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'Enter your email',
                      hintStyle: const TextStyle(color: Colors.white54),
                      prefixIcon:
                          const Icon(Icons.email, color: Colors.white70),
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
                  const SizedBox(height: 20),

                  // Reset method selector
                  Text(
                    'How would you like to receive the OTP?',
                    style: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Email option
                  _buildMethodRadio('email', '📧 Email', 'Get OTP via email'),

                  const SizedBox(height: 10),

                  // WhatsApp option
                  _buildMethodRadio(
                      'whatsapp', '💬 WhatsApp', 'Get OTP via WhatsApp'),

                  const SizedBox(height: 32),

                  // Request OTP Button
                  SizedBox(
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
                      onPressed: _resetService.isLoading ? null : _requestOtp,
                      child: _resetService.isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'Send OTP',
                              style: GoogleFonts.poppins(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                    ),
                  ),
                ] else if (_currentStep == 1) ...[
                  // OTP Input
                  TextField(
                    controller: _otpController,
                    style: const TextStyle(color: Colors.white),
                    keyboardType: TextInputType.number,
                    maxLength: 6,
                    decoration: InputDecoration(
                      hintText: '000000',
                      hintStyle: const TextStyle(color: Colors.white54),
                      prefixIcon:
                          const Icon(Icons.password, color: Colors.white70),
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
                  const SizedBox(height: 32),

                  // Verify OTP Button
                  SizedBox(
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
                      onPressed:
                          _resetService.isLoading ? null : _verifyOtp,
                      child: _resetService.isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'Verify OTP',
                              style: GoogleFonts.poppins(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                    ),
                  ),
                ] else if (_currentStep == 2) ...[
                  // New Password Input
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'New password',
                      hintStyle: const TextStyle(color: Colors.white54),
                      prefixIcon: const Icon(Icons.lock, color: Colors.white70),
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
                  const SizedBox(height: 16),

                  // Confirm Password Input
                  TextField(
                    controller: _confirmPasswordController,
                    obscureText: true,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'Confirm password',
                      hintStyle: const TextStyle(color: Colors.white54),
                      prefixIcon: const Icon(Icons.lock, color: Colors.white70),
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
                  const SizedBox(height: 32),

                  // Reset Password Button
                  SizedBox(
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
                      onPressed:
                          _resetService.isLoading ? null : _resetPassword,
                      child: _resetService.isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'Reset Password',
                              style: GoogleFonts.poppins(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );

  Widget _buildMethodRadio(
      String value, String title, String subtitle) => GestureDetector(
      onTap: () => setState(() => _resetMethod = value),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(
            color: _resetMethod == value ? Colors.white : Colors.white30,
          ),
          borderRadius: BorderRadius.circular(10),
          color: _resetMethod == value
              ? Colors.white.withOpacity(0.1)
              : Colors.transparent,
        ),
        child: Row(
          children: [
            Radio<String>(
              value: value,
              groupValue: _resetMethod,
              onChanged: (val) => setState(() => _resetMethod = val!),
              fillColor: const WidgetStatePropertyAll(Colors.white),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  subtitle,
                  style: GoogleFonts.roboto(
                    color: Colors.white70,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
}
