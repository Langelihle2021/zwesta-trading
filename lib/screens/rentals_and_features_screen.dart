import 'package:flutter/material.dart';
import '../widgets/logo_widget.dart';
import 'consolidated_reports_screen.dart';

class RentalsAndFeaturesScreen extends StatefulWidget {
  const RentalsAndFeaturesScreen({Key? key}) : super(key: key);

  @override
  State<RentalsAndFeaturesScreen> createState() =>
      _RentalsAndFeaturesScreenState();
}

class _RentalsAndFeaturesScreenState extends State<RentalsAndFeaturesScreen> {
  final List<Map<String, dynamic>> _rentals = [
    {
      'id': 'R001',
      'name': 'Premium Bot License',
      'type': 'Bot',
      'price': 99.99,
      'daysRemaining': 30,
      'status': 'Active',
    },
    {
      'id': 'R002',
      'name': 'API Access - High Volume',
      'type': 'API',
      'price': 49.99,
      'daysRemaining': 15,
      'status': 'Active',
    },
    {
      'id': 'R003',
      'name': 'Advanced Analytics',
      'type': 'Feature',
      'price': 29.99,
      'daysRemaining': 0,
      'status': 'Expired',
    },
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        elevation: 0,
        title: const Row(
          children: [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Rentals & Features'),
          ],
        ),
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
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.06),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: const Text(
                'Subscriptions and feature access are now aligned with the main mobile workflow.',
                style: TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ),
            // Active Rentals
            Text(
              'Active Subscriptions',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            ..._rentals
                .where((r) => r['status'] == 'Active')
                .map(
                  (rental) => Card(
                    color: const Color(0xFF1A1F3A),
                    margin: const EdgeInsets.only(bottom: 12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                rental['name'],
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.green,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  rental['status'],
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Type: ${rental['type']}',
                                style: const TextStyle(fontSize: 12),
                              ),
                              Text(
                                '\$${rental['price']}/month',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Days Remaining: ${rental['daysRemaining']}',
                            style: TextStyle(
                              fontSize: 12,
                              color: rental['daysRemaining'] < 10
                                  ? Colors.orange
                                  : Colors.grey,
                            ),
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    '${rental['name']} renewed for another month!',
                                  ),
                                ),
                              );
                            },
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 36),
                            ),
                            child: const Text('Renew'),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                ,
            const SizedBox(height: 24),

            // Expired/Available Features
            Text(
              'Available Upgrades',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 12),
            ..._rentals
                .where((r) => r['status'] == 'Expired')
                .map(
                  (rental) => Card(
                    color: const Color(0xFF1A1F3A),
                    margin: const EdgeInsets.only(bottom: 12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                rental['name'],
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.grey,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'Expired',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '\$${rental['price']}/month',
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    '${rental['name']} subscription activated!',
                                  ),
                                ),
                              );
                            },
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 36),
                            ),
                            child: const Text('Subscribe'),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                ,
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
}
