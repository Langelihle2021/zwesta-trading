import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../utils/environment_config.dart';

class JoinWithReferralScreen extends StatefulWidget {
  const JoinWithReferralScreen({Key? key}) : super(key: key);

  @override
  State<JoinWithReferralScreen> createState() => _JoinWithReferralScreenState();
}

class _JoinWithReferralScreenState extends State<JoinWithReferralScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _referralCodeController = TextEditingController();
  
  bool _isValidatingCode = false;
  bool _codeValid = false;
  String _referrerName = '';
  bool _isSubmitting = false;

  Future<void> _validateReferralCode(String code) async {
    if (code.isEmpty) return;

    setState(() => _isValidatingCode = true);
    try {
      final response = await http.get(
        Uri.parse(
            '${EnvironmentConfig.apiUrl}/api/referral/validate/${code.toUpperCase()}'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['valid'] == true) {
          setState(() {
            _codeValid = true;
            _referrerName = data['referrer_name'] ?? 'Unknown';
          });
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                    'Great! Referral code from ${data['referrer_name']} is valid'),
                backgroundColor: Colors.green,
              ),
            );
          }
        }
      } else {
        setState(() {
          _codeValid = false;
          _referrerName = '';
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Referral code not found'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      print('Error validating code: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Error validating code'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
    setState(() => _isValidatingCode = false);
  }

  Future<void> _registerUser() async {
    final name = _nameController.text.trim();
    final email = _emailController.text.trim();
    final referralCode = _referralCodeController.text.trim().toUpperCase();

    if (name.isEmpty || email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter name and email'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'name': name,
          'email': email,
          'referral_code': referralCode.isNotEmpty ? referralCode : null,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Account created successfully!'),
                backgroundColor: Colors.green,
              ),
            );
            // Navigate to home or dashboard
            Future.delayed(const Duration(seconds: 1), () {
              if (mounted) {
                Navigator.of(context).pop();
              }
            });
          }
        }
      } else {
        if (mounted) {
          final error = jsonDecode(response.body)['error'] ?? 'Registration failed';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(error),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      print('Error registering: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Error creating account'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
    setState(() => _isSubmitting = false);
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _referralCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Join with Referral'),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      backgroundColor: Colors.grey[850],
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Center(
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.card_giftcard,
                      size: 48,
                      color: Colors.blue,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Start Trading for FREE',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'No upfront payment. Earn nothing extra.',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Benefits
            Card(
              color: Colors.green.withOpacity(0.1),
              child: const Padding(
                padding: EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.check_circle, color: Colors.green, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'No Upfront Cost',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.check_circle, color: Colors.green, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Earn 5% from Your Recruits',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.check_circle, color: Colors.green, size: 20),
                        SizedBox(width: 8),
                        Text(
                          '30% Total Profit Share',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 32),

            // Referral Code Section
            Text(
              'Have a Referral Code?',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _referralCodeController,
              textCapitalization: TextCapitalization.characters,
              decoration: InputDecoration(
                labelText: 'Referral Code (Optional)',
                hintText: 'e.g., ABC123XY',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                suffixIcon: _isValidatingCode
                    ? const Padding(
                        padding: EdgeInsets.all(12),
                        child: SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                      )
                    : _codeValid
                        ? const Icon(Icons.check_circle, color: Colors.green)
                        : null,
              ),
              onChanged: (value) {
                if (value.length >= 8) {
                  _validateReferralCode(value);
                }
              },
            ),
            if (_codeValid)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Row(
                  children: [
                    const Icon(Icons.info, size: 16, color: Colors.green),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Referred by $_referrerName',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.green,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 24),

            // Personal Info
            Text(
              'Your Information',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nameController,
              decoration: InputDecoration(
                labelText: 'Full Name',
                hintText: 'John Doe',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              decoration: InputDecoration(
                labelText: 'Email Address',
                hintText: 'john@example.com',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Submit Button
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : _registerUser,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                ),
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text(
                        'Create Account & Start Free',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
              ),
            ),
            const SizedBox(height: 16),

            // Terms
            Center(
              child: Text(
                'By joining, you agree to our Terms of Service',
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.grey[500],
                ),
              ),
            ),
          ],
        ),
      ),
    );
}
