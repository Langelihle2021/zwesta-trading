import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';
import 'package:zwesta_trading_temp/themes/app_colors.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final mt5LoginController = TextEditingController();
  final mt5PasswordController = TextEditingController();
  double marginThreshold = 500;
  double priceThreshold = 100;
  bool isLoading = false;
  bool isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    mt5LoginController.dispose();
    mt5PasswordController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    setState(() => isLoading = true);
    final apiService = context.read<ApiService>();
    try {
      final data = await apiService.getUserSettings();
      setState(() {
        marginThreshold = (data['marginThreshold'] ?? 500).toDouble();
        priceThreshold = (data['priceThreshold'] ?? 100).toDouble();
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Failed to load settings')));
      }
    }
  }

  Future<void> _saveMt5Credentials() async {
    if (mt5LoginController.text.isEmpty || mt5PasswordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please fill all fields')));
      return;
    }

    setState(() => isSubmitting = true);
    final apiService = context.read<ApiService>();
    try {
      final success = await apiService.updateMt5Credentials(
        mt5LoginController.text,
        mt5PasswordController.text,
      );

      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('MT5 credentials updated')));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to update credentials')));
      }
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Error updating settings')));
    }
    setState(() => isSubmitting = false);
  }

  Future<void> _saveAlerts() async {
    setState(() => isSubmitting = true);
    final apiService = context.read<ApiService>();
    try {
      final success = await apiService.updateAlertSettings(
        marginThreshold,
        priceThreshold,
      );

      if (success) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Alerts updated')));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to update alerts')));
      }
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Error updating alerts')));
    }
    setState(() => isSubmitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: AppColors.darkBg,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // MT5 Credentials Section
                    Text(
                      'MT5 Credentials',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.cardBg,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        children: [
                          TextField(
                            controller: mt5LoginController,
                            decoration: InputDecoration(
                              labelText: 'MT5 Login',
                              prefixIcon: const Icon(Icons.person),
                              filled: true,
                              fillColor: AppColors.darkBg,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                                borderSide: BorderSide.none,
                              ),
                            ),
                          ),
                          const SizedBox(height: 12),
                          TextField(
                            controller: mt5PasswordController,
                            obscureText: true,
                            decoration: InputDecoration(
                              labelText: 'MT5 Password',
                              prefixIcon: const Icon(Icons.lock),
                              filled: true,
                              fillColor: AppColors.darkBg,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                                borderSide: BorderSide.none,
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: isSubmitting ? null : _saveMt5Credentials,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.primary,
                                padding:
                                    const EdgeInsets.symmetric(vertical: 16),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                              ),
                              child: Text(
                                isSubmitting ? 'Updating...' : 'Save MT5 Credentials',
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Alert Settings Section
                    Text(
                      'Alert Settings',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.cardBg,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Margin Threshold',
                                style: Theme.of(context).textTheme.bodyLarge,
                              ),
                              Text(
                                '${marginThreshold.toStringAsFixed(0)}%',
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(color: AppColors.primary),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Slider(
                            value: marginThreshold,
                            min: 100,
                            max: 1000,
                            divisions: 18,
                            activeColor: AppColors.primary,
                            onChanged: (value) {
                              setState(() => marginThreshold = value);
                            },
                          ),
                          const SizedBox(height: 24),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Price Change Alert (\$)',
                                style: Theme.of(context).textTheme.bodyLarge,
                              ),
                              Text(
                                '\$${priceThreshold.toStringAsFixed(2)}',
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(color: AppColors.primary),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Slider(
                            value: priceThreshold,
                            min: 10,
                            max: 500,
                            divisions: 49,
                            activeColor: AppColors.primary,
                            onChanged: (value) {
                              setState(() => priceThreshold = value);
                            },
                          ),
                          const SizedBox(height: 24),
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton(
                              onPressed: isSubmitting ? null : _saveAlerts,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.primary,
                                padding:
                                    const EdgeInsets.symmetric(vertical: 16),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                              ),
                              child: Text(
                                isSubmitting ? 'Saving...' : 'Save Alert Settings',
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
