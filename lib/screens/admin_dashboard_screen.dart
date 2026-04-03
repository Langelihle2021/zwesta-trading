import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';
import 'bot_strategy_configuration_screen.dart';
import 'consolidated_reports_screen.dart';
import 'symbol_management_screen.dart';
import 'user_account_management_screen.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({Key? key}) : super(key: key);

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  late Future<Map<String, dynamic>> _adminData;

  @override
  void initState() {
    super.initState();
    _adminData = _fetchAdminData();
  }

  Future<Map<String, dynamic>> _fetchAdminData() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/admin/dashboard'),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return {};
    } catch (e) {
      print('Error fetching admin data: $e');
      return {};
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _adminData = _fetchAdminData();
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Admin Dashboard'),
          ],
        ),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.home_outlined),
            tooltip: 'Home',
            onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
          ),
          IconButton(
            icon: const Icon(Icons.assessment_outlined),
            tooltip: 'Reports',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const ConsolidatedReportsScreen()));
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      backgroundColor: Colors.grey[850],
      body: FutureBuilder<Map<String, dynamic>>(
        future: _adminData,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          final data = snapshot.data ?? {};
          final totalUsers = data['total_users'] ?? 0;
          final totalBots = data['total_bots'] ?? 0;
          final platformEarnings = (data['platform_earnings'] ?? 0.0).toDouble();
          final totalProfit = (data['total_profit'] ?? 0.0).toDouble();
          final users = data['users'] ?? [];

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Key Metrics
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  children: [
                    _StatCard(
                      title: 'Total Users',
                      value: totalUsers.toString(),
                      icon: Icons.people,
                      color: Colors.blue,
                    ),
                    _StatCard(
                      title: 'Active Bots',
                      value: totalBots.toString(),
                      icon: Icons.smart_toy,
                      color: Colors.green,
                    ),
                    _StatCard(
                      title: 'Platform Earnings',
                      value: '\$${platformEarnings.toStringAsFixed(2)}',
                      icon: Icons.trending_up,
                      color: Colors.orange,
                    ),
                    _StatCard(
                      title: 'Total Client Profit',
                      value: '\$${totalProfit.toStringAsFixed(2)}',
                      icon: Icons.attach_money,
                      color: Colors.purple,
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Commission Breakdown
                Card(
                  color: Colors.grey[800],
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Commission Breakdown',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 16),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Platform Share (25%)',
                                  style: TextStyle(fontSize: 12),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '\$${platformEarnings.toStringAsFixed(2)}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18,
                                    color: Colors.orange,
                                  ),
                                ),
                              ],
                            ),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                const Text(
                                  'Referrer Share (5%)',
                                  style: TextStyle(fontSize: 12),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '\$${(platformEarnings * 0.2).toStringAsFixed(2)}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18,
                                    color: Colors.blue,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        const Divider(),
                        const SizedBox(height: 12),
                        const Text(
                          r'Revenue Model: $100 profit → $25 to platform, $5 to referrer, $70 to client',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Management Tools
                Text(
                  'Management Tools',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                GridView.count(
                  crossAxisCount: 3,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  children: [
                    _ManagementCard(
                      title: 'Symbols',
                      icon: Icons.currency_exchange,
                      color: Colors.blue,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const SymbolManagementScreen(),
                          ),
                        );
                      },
                    ),
                    _ManagementCard(
                      title: 'Users',
                      icon: Icons.people,
                      color: Colors.green,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const UserAccountManagementScreen(),
                          ),
                        );
                      },
                    ),
                    _ManagementCard(
                      title: 'Strategies',
                      icon: Icons.psychology,
                      color: Colors.orange,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const BotStrategyConfigurationScreen(),
                          ),
                        );
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Active Users & Bots
                Text(
                  'Active Users & Their Bots',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                if (users.isEmpty)
                  const Card(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Center(
                        child: Column(
                          children: [
                            Icon(
                              Icons.people_outline,
                              size: 48,
                              color: Colors.grey,
                            ),
                            SizedBox(height: 12),
                            Text('No active users yet'),
                          ],
                        ),
                      ),
                    ),
                  )
                else
                  ListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: users.length,
                    itemBuilder: (context, index) {
                      final user = users[index];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          user['name'] ?? 'Unknown',
                                          style: const TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 14,
                                          ),
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          user['email'] ?? '',
                                          style: const TextStyle(
                                            fontSize: 11,
                                            color: Colors.grey,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Text(
                                        '${user['bot_count'] ?? 0} bots',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.blue,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '\$${(user['total_profit'] ?? 0).toStringAsFixed(2)}',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          fontSize: 12,
                                          color: Colors.green,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              if ((user['bots'] as List?)?.isNotEmpty ?? false)
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text(
                                      'Active Bots:',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.grey,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Wrap(
                                      spacing: 4,
                                      children: (user['bots'] as List?)
                                              ?.map<Widget>((bot) => Chip(
                                                    label: Text(
                                                      bot['botId'] ?? 'Unknown',
                                                      style:
                                                          const TextStyle(
                                                        fontSize: 10,
                                                      ),
                                                    ),
                                                    backgroundColor:
                                                        Colors.blue
                                                            .withOpacity(0.3),
                                                  ))
                                              .toList() ??
                                          [],
                                    ),
                                  ],
                                ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
              ],
            ),
          );
        },
      ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: const Color(0xFF111633),
        selectedItemColor: const Color(0xFF00E5FF),
        unselectedItemColor: Colors.white38,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_rounded),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.assessment_outlined),
            label: 'Reports',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.admin_panel_settings),
            label: 'Admin',
          ),
        ],
        currentIndex: 2,
        onTap: (index) {
          if (index == 0) {
            Navigator.of(context).popUntil((route) => route.isFirst);
          } else if (index == 1) {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (context) => const ConsolidatedReportsScreen()),
            );
          }
        },
      ),
    );
}

class _StatCard extends StatelessWidget {

  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => Card(
      color: Colors.grey[800],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 12),
            Text(
              value,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 20,
                color: color,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              title,
              style: const TextStyle(
                fontSize: 11,
                color: Colors.grey,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
}

class _ManagementCard extends StatelessWidget {

  const _ManagementCard({
    required this.title,
    required this.icon,
    required this.color,
    required this.onTap,
  });
  final String title;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => GestureDetector(
      onTap: onTap,
      child: Card(
        color: Colors.grey[800],
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 40),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
}
