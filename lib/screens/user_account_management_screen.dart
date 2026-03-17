import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/logo_widget.dart';

class UserAccountManagementScreen extends StatefulWidget {
  const UserAccountManagementScreen({Key? key}) : super(key: key);

  @override
  State<UserAccountManagementScreen> createState() => _UserAccountManagementScreenState();
}

class _UserAccountManagementScreenState extends State<UserAccountManagementScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _users = [];
  bool _isLoading = true;
  String _selectedUser = '';
  dynamic _selectedUserDetails;

  final List<String> _brokers = ['Exness', 'IG', 'OANDA', 'FXCM', 'Binance'];

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    try {
      setState(() => _isLoading = true);
      final response = await _apiService.get('/api/admin/users');

      if (response['success'] == true) {
        setState(() {
          _users = response['users'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading users: $e'), duration: const Duration(seconds: 3)),
      );
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadUserDetails(String userId) async {
    try {
      final response = await _apiService.get('/api/admin/users/$userId');

      if (response['success'] == true) {
        setState(() {
          _selectedUserDetails = response;
          _selectedUser = userId;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading user details: $e'), duration: const Duration(seconds: 3)),
      );
    }
  }

  Future<void> _createUser() async {
    final formKey = GlobalKey<FormState>();
    String? email, name;

    await showDialog(
      context: context,
      builder: (BuildContext context) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Create New User',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) {
                      if (value?.isEmpty ?? true) return 'Required';
                      if (!value!.contains('@')) return 'Invalid email';
                      return null;
                    },
                    onSaved: (value) => email = value,
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Full Name',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => name = value,
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton(
                        onPressed: () async {
                          if (formKey.currentState?.validate() ?? false) {
                            formKey.currentState?.save();
                            Navigator.pop(context);

                            try {
                              final response = await _apiService.post('/api/admin/users/create', {
                                'email': email,
                                'name': name,
                              });

                              if (response['success'] == true) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('User created! Referral Code: ${response['referral_code']}'),
                                    duration: const Duration(seconds: 3),
                                  ),
                                );
                                _loadUsers();
                              }
                            } catch (e) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                              );
                            }
                          }
                        },
                        child: const Text('Create User'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _addUserAccount(String userId) async {
    final formKey = GlobalKey<FormState>();
    String? accountId, broker;
    double? balance;

    await showDialog(
      context: context,
      builder: (BuildContext context) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Add Trading Account',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Account ID',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => accountId = value,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      labelText: 'Broker',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _brokers.map((b) => DropdownMenuItem(value: b, child: Text(b))).toList(),
                    onChanged: (value) => broker = value,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Initial Balance',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    keyboardType: TextInputType.number,
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => balance = double.tryParse(value ?? '0'),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton(
                        onPressed: () async {
                          if (formKey.currentState?.validate() ?? false) {
                            formKey.currentState?.save();
                            Navigator.pop(context);

                            try {
                              final response = await _apiService.post('/api/user/accounts/add', {
                                'account_id': accountId,
                                'broker': broker,
                                'balance': balance,
                              });

                              if (response['success'] == true) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Account added successfully'),
                                    duration: Duration(seconds: 2),
                                  ),
                                );
                                _loadUserDetails(userId);
                              }
                            } catch (e) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                              );
                            }
                          }
                        },
                        child: const Text('Add Account'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: const [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('User Account Management'),
          ],
        ),
        backgroundColor: Colors.deepPurple,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Row(
              children: [
                // Users List
                SizedBox(
                  width: 300,
                  child: Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(10),
                        child: ElevatedButton.icon(
                          onPressed: _createUser,
                          icon: const Icon(Icons.person_add),
                          label: const Text('Add User'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.deepPurple,
                            minimumSize: const Size(double.infinity, 45),
                          ),
                        ),
                      ),
                      Expanded(
                        child: ListView.builder(
                          itemCount: _users.length,
                          itemBuilder: (context, index) {
                            final user = _users[index];
                            bool isSelected = _selectedUser == user['user_id'];
                            return ListTile(
                              selected: isSelected,
                              selectedTileColor: Colors.deepPurple.withAlpha(100),
                              title: Text(user['name'] ?? 'Unknown'),
                              subtitle: Text(
                                user['email'] ?? 'N/A',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              onTap: () => _loadUserDetails(user['user_id']),
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
                // User Details
                Expanded(
                  child: _selectedUserDetails == null
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.person_outline, size: 80, color: Colors.grey.shade300),
                              const SizedBox(height: 20),
                              Text(
                                'Select a user to view details',
                                style: TextStyle(fontSize: 16, color: Colors.grey.shade600),
                              ),
                            ],
                          ),
                        )
                      : SingleChildScrollView(
                          padding: const EdgeInsets.all(20),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // User Info Card
                              Card(
                                child: Padding(
                                  padding: const EdgeInsets.all(15),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _selectedUserDetails['user']['name'] ?? 'N/A',
                                        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                                      ),
                                      const SizedBox(height: 10),
                                      Text('Email: ${_selectedUserDetails['user']['email']}'),
                                      Text('User ID: ${_selectedUserDetails['user']['user_id']}'),
                                      Text('Referral Code: ${_selectedUserDetails['user']['referral_code']}'),
                                      Text(
                                        'Total Commission: \$${_selectedUserDetails['user']['total_commission']?.toStringAsFixed(2) ?? '0.00'}',
                                        style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.green),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                              const SizedBox(height: 20),
                              // Trading Accounts
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  const Text(
                                    'Trading Accounts',
                                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                  ElevatedButton.icon(
                                    onPressed: () => _addUserAccount(_selectedUser),
                                    icon: const Icon(Icons.add),
                                    label: const Text('Add Account'),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              ...((_selectedUserDetails['accounts'] as List?)?.isEmpty ?? true
                                  ? [
                                      Padding(
                                        padding: const EdgeInsets.symmetric(vertical: 20),
                                        child: Center(
                                          child: Text(
                                            'No accounts linked',
                                            style: TextStyle(color: Colors.grey.shade600),
                                          ),
                                        ),
                                      ),
                                    ]
                                  : (_selectedUserDetails['accounts'] as List)
                                      .map(
                                        (account) => Card(
                                          margin: const EdgeInsets.symmetric(vertical: 8),
                                          child: ListTile(
                                            title: Text('${account['broker']} - ${account['account_id']}'),
                                            subtitle: Text(
                                              'Balance: \$${account['balance']?.toStringAsFixed(2) ?? '0.00'} • Profit: \$${account['cumulative_profit']?.toStringAsFixed(2) ?? '0.00'}',
                                            ),
                                          ),
                                        ),
                                      )
                                      .toList()),
                              const SizedBox(height: 20),
                              // Trading Settings
                              const Text(
                                'Trading Settings',
                                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 10),
                              Card(
                                child: Padding(
                                  padding: const EdgeInsets.all(15),
                                  child: (_selectedUserDetails['settings']?.isNotEmpty ?? false)
                                      ? Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                                'Risk Profile: ${_selectedUserDetails['settings']['risk_profile'] ?? 'N/A'}'),
                                            Text(
                                                'Max Daily Loss: \$${_selectedUserDetails['settings']['max_daily_loss'] ?? '0'}'),
                                            Text(
                                                'Default Leverage: ${_selectedUserDetails['settings']['default_leverage'] ?? 'N/A'}x'),
                                          ],
                                        )
                                      : Text(
                                          'No custom settings',
                                          style: TextStyle(color: Colors.grey.shade600),
                                        ),
                                ),
                              ),
                            ],
                          ),
                        ),
                ),
              ],
            ),
    );
  }
}
