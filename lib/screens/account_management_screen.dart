import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/auth_service.dart';
import '../services/trading_service.dart';
import '../utils/constants.dart';
import 'broker_integration_screen.dart';
import 'commission_dashboard_screen.dart';

class AccountManagementScreen extends StatefulWidget {
  const AccountManagementScreen({Key? key}) : super(key: key);

  @override
  State<AccountManagementScreen> createState() => _AccountManagementScreenState();
}

class _AccountManagementScreenState extends State<AccountManagementScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: 'Account Management',
        showBackButton: true,
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Profile'),
            Tab(text: 'Accounts'),
            Tab(text: 'Settings'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildProfileTab(),
          _buildAccountsTab(),
          _buildSettingsTab(),
        ],
      ),
    );
  }

  Widget _buildProfileTab() {
    return Consumer<AuthService>(
      builder: (context, authService, _) {
        return SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Profile Header
              Center(
                child: Column(
                  children: [
                    Container(
                      width: 100,
                      height: 100,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppColors.primaryColor.withOpacity(0.2),
                      ),
                      child: const Icon(
                        Icons.person,
                        size: 50,
                        color: AppColors.primaryColor,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      authService.currentUser?.fullName ?? 'User',
                      style: Theme.of(context).textTheme.displaySmall,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      authService.currentUser?.email ?? '',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md,
                        vertical: AppSpacing.sm,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.primaryColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        authService.currentUser?.accountType ?? 'Standard',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: AppColors.primaryColor,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.xl),

              // Profile Form
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: _buildEditProfileForm(context, authService),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildEditProfileForm(BuildContext context, AuthService authService) {
    final firstNameController =
        TextEditingController(text: authService.currentUser?.firstName);
    final lastNameController =
        TextEditingController(text: authService.currentUser?.lastName);
    final emailController =
        TextEditingController(text: authService.currentUser?.email);

    return Column(
      children: [
        Text(
          'Edit Profile',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: firstNameController,
          decoration: const InputDecoration(
            labelText: 'First Name',
            prefixIcon: Icon(Icons.person),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: lastNameController,
          decoration: const InputDecoration(
            labelText: 'Last Name',
            prefixIcon: Icon(Icons.person),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: emailController,
          decoration: const InputDecoration(
            labelText: 'Email',
            prefixIcon: Icon(Icons.email),
          ),
          keyboardType: TextInputType.emailAddress,
        ),
        const SizedBox(height: AppSpacing.lg),
        Consumer<AuthService>(
          builder: (context, authService, _) {
            return ElevatedButton(
              onPressed: authService.isLoading
                  ? null
                  : () async {
                      final success = await authService.updateProfile(
                        firstNameController.text,
                        lastNameController.text,
                        emailController.text,
                      );
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              success
                                  ? 'Profile updated successfully'
                                  : 'Failed to update profile',
                            ),
                          ),
                        );
                      }
                    },
              child: authService.isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Text('Update Profile'),
            );
          },
        ),
      ],
    );
  }

  Widget _buildAccountsTab() {
    return Consumer<TradingService>(
      builder: (context, tradingService, _) {
        return ListView(
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            // Broker integration quick link
            FutureBuilder<SharedPreferences>(
              future: SharedPreferences.getInstance(),
              builder: (ctx, snap) {
                if (!snap.hasData) return const SizedBox.shrink();
                final prefs = snap.data!;
                final broker = prefs.getString('broker');
                final connected = prefs.getBool('broker_connected') == true;
                final balance = prefs.getDouble('account_balance') ?? 0;
                return Card(
                  margin: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: Column(
                    children: [
                      ListTile(
                        leading: Icon(connected ? Icons.link : Icons.link_off, color: connected ? Colors.green : Colors.orange),
                        title: Text(connected ? 'Broker: ${broker ?? "Unknown"}' : 'No Broker Connected'),
                        subtitle: connected ? Text('Balance: \$${balance.toStringAsFixed(2)}') : const Text('Tap to connect your trading account'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BrokerIntegrationScreen())),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        leading: const Icon(Icons.monetization_on, color: Colors.green),
                        title: const Text('View Commissions'),
                        subtitle: const Text('Earnings & withdrawal history'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CommissionDashboardScreen())),
                      ),
                    ],
                  ),
                );
              },
            ),
            // Trading accounts list
            ...List.generate(tradingService.accounts.length, (index) {
            final account = tradingService.accounts[index];
            return Card(
              margin: const EdgeInsets.only(bottom: AppSpacing.md),
              child: ExpansionTile(
                title: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      account.accountNumber,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'Balance: \$${account.balance.toStringAsFixed(2)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
                subtitle: Container(
                  margin: const EdgeInsets.only(top: AppSpacing.sm),
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: AppSpacing.xs,
                  ),
                  decoration: BoxDecoration(
                    color: account.isActive
                        ? AppColors.successColor.withOpacity(0.1)
                        : AppColors.warningColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    account.status.toUpperCase(),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: account.isActive
                          ? AppColors.successColor
                          : AppColors.warningColor,
                    ),
                  ),
                ),
                children: [
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildDetailRow('Account ID', account.id),
                        _buildDetailRow('Currency', account.currency),
                        _buildDetailRow('Leverage', account.leverage),
                        _buildDetailRow(
                          'Used Margin',
                          '\$${account.usedMargin.toStringAsFixed(2)}',
                        ),
                        _buildDetailRow(
                          'Available Margin',
                          '\$${account.availableMargin.toStringAsFixed(2)}',
                        ),
                        _buildDetailRow(
                          'Margin Usage',
                          '${account.marginUsagePercentage.toStringAsFixed(2)}%',
                        ),
                        _buildDetailRow(
                          'Created',
                          account.createdAt.toString().split(' ')[0],
                        ),
                        const SizedBox(height: AppSpacing.md),
                        if (account.marginUsagePercentage > 80)
                          Container(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            decoration: BoxDecoration(
                              color: AppColors.warningColor.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.warning,
                                  color: AppColors.warningColor,
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Text(
                                    'High margin usage. Consider closing some positions.',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(
                                          color: AppColors.warningColor,
                                        ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
          ],
        );
      },
    );
  }

  Widget _buildSettingsTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Security Section
          Text(
            'Security',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: ListTile(
              leading: const Icon(Icons.lock),
              title: const Text('Change Password'),
              subtitle: Text(
                'Update your password regularly',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              trailing: const Icon(Icons.arrow_forward),
              onTap: () => _showChangePasswordDialog(),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: ListTile(
              leading: const Icon(Icons.security),
              title: const Text('Two-Factor Authentication'),
              subtitle: Text(
                'Secure your account',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              trailing: Switch(value: false, onChanged: (_) {}),
            ),
          ),

          const SizedBox(height: AppSpacing.lg),

          // Preferences Section
          Text(
            'Preferences',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: ListTile(
              leading: const Icon(Icons.notifications),
              title: const Text('Notifications'),
              trailing: Switch(value: true, onChanged: (_) {}),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: ListTile(
              leading: const Icon(Icons.dark_mode),
              title: const Text('Dark Mode'),
              trailing: Switch(value: false, onChanged: (_) {}),
            ),
          ),

          const SizedBox(height: AppSpacing.lg),

          // Account Section
          Text(
            'Account',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: ListTile(
              leading: const Icon(Icons.delete),
              title: const Text('Delete Account'),
              subtitle: Text(
                'Permanently delete your account',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              trailing: const Icon(Icons.arrow_forward),
              textColor: AppColors.dangerColor,
              onTap: () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Delete Account'),
                    content: const Text(
                      'Are you sure you want to permanently delete your account? This action cannot be undone.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.dangerColor,
                        ),
                        child: const Text('Delete'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: AppSpacing.lg),

          // About Section
          Text(
            'About',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.md),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                children: [
                  _buildDetailRow('App Version', '1.0.0'),
                  _buildDetailRow('Build', '1'),
                  _buildDetailRow('API Version', 'v1.0'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showChangePasswordDialog() {
    final oldPasswordController = TextEditingController();
    final newPasswordController = TextEditingController();
    final confirmPasswordController = TextEditingController();
    bool obscureOld = true;
    bool obscureNew = true;
    bool obscureConfirm = true;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: const Text('Change Password'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: oldPasswordController,
                  obscureText: obscureOld,
                  decoration: InputDecoration(
                    labelText: 'Old Password',
                    prefixIcon: const Icon(Icons.lock),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscureOld ? Icons.visibility_off : Icons.visibility,
                      ),
                      onPressed: () {
                        setState(() => obscureOld = !obscureOld);
                      },
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: newPasswordController,
                  obscureText: obscureNew,
                  decoration: InputDecoration(
                    labelText: 'New Password',
                    prefixIcon: const Icon(Icons.lock),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscureNew ? Icons.visibility_off : Icons.visibility,
                      ),
                      onPressed: () {
                        setState(() => obscureNew = !obscureNew);
                      },
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: confirmPasswordController,
                  obscureText: obscureConfirm,
                  decoration: InputDecoration(
                    labelText: 'Confirm Password',
                    prefixIcon: const Icon(Icons.lock),
                    suffixIcon: IconButton(
                      icon: Icon(
                        obscureConfirm ? Icons.visibility_off : Icons.visibility,
                      ),
                      onPressed: () {
                        setState(() => obscureConfirm = !obscureConfirm);
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            Consumer<AuthService>(
              builder: (context, authService, _) {
                return ElevatedButton(
                  onPressed: authService.isLoading
                      ? null
                      : () async {
                          if (newPasswordController.text !=
                              confirmPasswordController.text) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Passwords do not match'),
                              ),
                            );
                            return;
                          }
                          final success = await authService.changePassword(
                            oldPasswordController.text,
                            newPasswordController.text,
                          );
                          if (mounted) {
                            Navigator.pop(context);
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  success
                                      ? 'Password changed successfully'
                                      : 'Failed to change password',
                                ),
                              ),
                            );
                          }
                        },
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
                      : const Text('Change Password'),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(value),
        ],
      ),
    );
  }
}
