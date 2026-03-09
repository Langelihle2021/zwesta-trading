import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../widgets/custom_widgets.dart';
import '../widgets/logo_widget.dart';
import 'forgot_password_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late TextEditingController _usernameController;
  late TextEditingController _passwordController;
  bool _obscurePassword = true;
  bool _isLogin = true;
  bool _showForgotPassword = false;
  late TextEditingController _emailController;
  late TextEditingController _firstNameController;
  late TextEditingController _lastNameController;

  @override
  void initState() {
    super.initState();
    _usernameController = TextEditingController();
    _passwordController = TextEditingController();
    _emailController = TextEditingController();
    _firstNameController = TextEditingController();
    _lastNameController = TextEditingController();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
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

    return Scaffold(
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
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Logo Header
                SizedBox(height: MediaQuery.of(context).size.height * 0.05),
                const LogoWidget(size: 200, showText: true),
                const SizedBox(height: AppSpacing.lg),
                Text(
                  _isLogin ? 'Welcome Back' : 'Create Your Account',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),

                // Error Banner
                Consumer<AuthService>(
                  builder: (context, authService, _) {
                    if (authService.errorMessage != null) {
                      return Column(
                        children: [
                          ErrorBanner(
                            message: authService.errorMessage!,
                            onDismiss: () {
                              authService.clearErrorMessage();
                            },
                          ),
                          const SizedBox(height: AppSpacing.md),
                        ],
                      );
                    }
                    return const SizedBox.shrink();
                  },
                ),

                // Form Fields
                if (_isLogin)
                  _buildLoginForm()
                else
                  _buildRegisterForm(),

                const SizedBox(height: AppSpacing.lg),

                // Login/Register Button
                Consumer<AuthService>(
                  builder: (context, authService, _) {
                    return ElevatedButton(
                      onPressed: authService.isLoading ? null : _handleSubmit,
                      child: authService.isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor:
                                    AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            )
                          : Text(_isLogin ? 'Login' : 'Register'),
                    );
                  },
                ),

                const SizedBox(height: AppSpacing.md),

                // Toggle Login/Register
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      _isLogin
                          ? "Don't have an account? "
                          : 'Already have an account? ',
                      style: GoogleFonts.roboto(
                        color: Colors.white70,
                        fontSize: 14,
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        setState(() {
                          _isLogin = !_isLogin;
                        });
                        context.read<AuthService>().clearErrorMessage();
                      },
                      child: Text(
                        _isLogin ? 'Register' : 'Login',
                        style: GoogleFonts.poppins(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),

                // Forgot Password Link (only on login)
                if (_isLogin)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8.0),
                    child: TextButton(
                      onPressed: () {
                        setState(() => _showForgotPassword = true);
                      },
                      child: Text(
                        'Forgot Password?',
                        style: GoogleFonts.roboto(
                          color: Colors.white70,
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),

                const SizedBox(height: AppSpacing.xl),

                // Demo Credentials
                Container(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.white24),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Demo Credentials:',
                        style: GoogleFonts.poppins(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        'Username: demo',
                        style: GoogleFonts.roboto(
                          color: Colors.white70,
                          fontSize: 12,
                        ),
                      ),
                      Text(
                        'Password: demo123',
                        style: GoogleFonts.roboto(
                          color: Colors.white70,
                          fontSize: 12,
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
    );
  }

  Widget _buildLoginForm() {
    return Column(
      children: [
        TextField(
          controller: _usernameController,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            labelText: 'Username',
            labelStyle: const TextStyle(color: Colors.white70),
            hintText: 'Enter your username',
            hintStyle: const TextStyle(color: Colors.white54),
            prefixIcon: const Icon(Icons.person, color: Colors.white70),
            filled: true,
            fillColor: Colors.white.withOpacity(0.1),
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
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _passwordController,
          obscureText: _obscurePassword,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            labelText: 'Password',
            labelStyle: const TextStyle(color: Colors.white70),
            hintText: 'Enter your password',
            hintStyle: const TextStyle(color: Colors.white54),
            prefixIcon: const Icon(Icons.lock, color: Colors.white70),
            filled: true,
            fillColor: Colors.white.withOpacity(0.1),
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
            suffixIcon: IconButton(
              icon: Icon(
                _obscurePassword ? Icons.visibility_off : Icons.visibility,
                color: Colors.white70,
              ),
              onPressed: () {
                setState(() {
                  _obscurePassword = !_obscurePassword;
                });
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRegisterForm() {
    return Column(
      children: [
        TextField(
          controller: _firstNameController,
          decoration: const InputDecoration(
            labelText: 'First Name',
            hintText: 'Enter your first name',
            prefixIcon: Icon(Icons.person),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _lastNameController,
          decoration: const InputDecoration(
            labelText: 'Last Name',
            hintText: 'Enter your last name',
            prefixIcon: Icon(Icons.person),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _usernameController,
          decoration: const InputDecoration(
            labelText: 'Username',
            hintText: 'Choose a username',
            prefixIcon: Icon(Icons.person),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _emailController,
          decoration: const InputDecoration(
            labelText: 'Email',
            hintText: 'Enter your email',
            prefixIcon: Icon(Icons.email),
          ),
          keyboardType: TextInputType.emailAddress,
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _passwordController,
          obscureText: _obscurePassword,
          decoration: InputDecoration(
            labelText: 'Password',
            hintText: 'Create a password',
            prefixIcon: const Icon(Icons.lock),
            suffixIcon: IconButton(
              icon: Icon(
                _obscurePassword ? Icons.visibility_off : Icons.visibility,
              ),
              onPressed: () {
                setState(() {
                  _obscurePassword = !_obscurePassword;
                });
              },
            ),
          ),
        ),
      ],
    );
  }

  void _handleSubmit() {
    final authService = context.read<AuthService>();

    if (_isLogin) {
      authService.login(
        _usernameController.text,
        _passwordController.text,
      );
    } else {
      authService.register(
        _usernameController.text,
        _emailController.text,
        _passwordController.text,
        _firstNameController.text,
        _lastNameController.text,
      );
    }
  }
}
