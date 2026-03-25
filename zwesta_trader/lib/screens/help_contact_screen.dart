import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class HelpContactScreen extends StatefulWidget {
  const HelpContactScreen({Key? key}) : super(key: key);

  @override
  State<HelpContactScreen> createState() => _HelpContactScreenState();
}

class _HelpContactScreenState extends State<HelpContactScreen> {
  int _selectedTab = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset(
              'assets/images/logo.jpeg',
              width: 40,
              height: 40,
              fit: BoxFit.contain,
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ZWESTA',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Text(
                  'HELP & SUPPORT',
                  style: TextStyle(fontSize: 10, color: Colors.cyanAccent),
                ),
              ],
            ),
          ],
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Tab Buttons
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: _buildTabButton(0, 'FAQ', Icons.help),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildTabButton(1, 'Issues', Icons.bug_report),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _buildTabButton(2, 'Contact', Icons.contact_mail),
                ),
              ],
            ),
          ),
          // Content
          Expanded(
            child: IndexedStack(
              index: _selectedTab,
              children: [
                _buildFAQTab(),
                _buildIssuesTab(),
                _buildContactTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTabButton(int index, String label, IconData icon) {
    final isSelected = _selectedTab == index;
    return ElevatedButton.icon(
      onPressed: () => setState(() => _selectedTab = index),
      icon: Icon(icon, size: 16),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        backgroundColor: isSelected ? Colors.cyan : Colors.grey.shade700,
        foregroundColor: isSelected ? Colors.black : Colors.white,
      ),
    );
  }

  Widget _buildFAQTab() {
    const faqs = [
      ('What is Zwesta Trading?', 'Professional automated trading system for MT5 brokers'),
      ('Supported Brokers?', 'XM Global, IC Markets, Pepperstone, FXCM'),
      ('What are Safety Features?', 'Daily/Session loss limits, consecutive loss limits, economic event avoidance'),
      ('Demo Accounts?', 'Yes, fully supported with same features as LIVE accounts'),
      ('Multi-Account Support?', 'Yes, manage multiple accounts from different brokers'),
      ('Economic Event Avoidance?', '40+ major events, 30-minute automatic avoidance windows'),
      ('Multi-User System?', 'Complete support for multiple traders with separate credentials'),
      ('Reconnection Handling?', 'Automatic reconnection with exponential backoff (5-60 seconds)'),
    ];

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: faqs.length,
      itemBuilder: (context, index) {
        final (question, answer) = faqs[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ExpansionTile(
            title: Text(question),
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(answer),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildIssuesTab() {
    const issues = [
      (
        'Connection Failed',
        [
          '✓ Check your internet connection',
          '✓ Verify MT5 account credentials',
          '✓ Ensure broker server is accessible',
          '✓ Try logging in manually to MT5',
          '✓ Check firewall/antivirus settings',
        ]
      ),
      (
        'Orders Not Executing',
        [
          '✓ Check if account is in trading mode',
          '✓ Verify sufficient margin available',
          '✓ Confirm trading hours for your broker',
          '✓ Check for active restrictions on symbol',
          '✓ Review recent loss limits',
        ]
      ),
      (
        'Insufficient Balance/Margin',
        [
          '✓ Check account balance from broker dashboard',
          '✓ Verify leverage setting (default 1:500)',
          '✓ Calculate minimum margin needed',
          r'  • For 0.01 lot EUR/USD: ~$1-10 depending on leverage',
          '✓ Reduce position size in settings',
        ]
      ),
      (
        'Trade Journal Empty',
        [
          '✓ Ensure trades have been executed',
          '✓ Check database sync status',
          '✓ Verify account connection is active',
          '✓ Allow time for journal to populate',
          '✓ Restart app if needed',
        ]
      ),
    ];

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: issues.length,
      itemBuilder: (context, index) {
        final (title, solutions) = issues[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ExpansionTile(
            title: Text(title),
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ...solutions.map((s) => Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(s),
                        )),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => _sendWhatsApp('issue: $title'),
                        child: const Text('Report Issue via WhatsApp'),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildContactTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // WhatsApp Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  const Icon(Icons.phone, size: 48, color: Colors.green),
                  const SizedBox(height: 12),
                  const Text(
                    'WhatsApp Support',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '+27696469651',
                    style: TextStyle(fontSize: 16, color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Support Hours: Mon-Fri 09:00-18:00 SAST, Sat 10:00-14:00 SAST',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () => _sendWhatsApp('Hello, I need support'),
                      icon: const Icon(Icons.chat),
                      label: const Text('Open WhatsApp'),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Support Types
          const Text(
            'Select Support Type',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          _buildSupportButton(
            '🐛 Report a Bug',
            'Report technical issues',
            'bug report',
          ),
          _buildSupportButton(
            '⚙️ Configuration Help',
            'Help with setup and settings',
            'config help',
          ),
          _buildSupportButton(
            '📈 Trading Strategy',
            'Discuss trading approaches',
            'strategy',
          ),
          _buildSupportButton(
            '💡 Feature Request',
            'Suggest new features',
            'feature request',
          ),
        ],
      ),
    );
  }

  Widget _buildSupportButton(String title, String subtitle, String type) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => _sendWhatsApp('Support type: $type'),
      ),
    );
  }

  Future<void> _sendWhatsApp(String message) async {
    final encodeMessage = Uri.encodeComponent(message);
    final whatsappUrl = Uri.parse('https://wa.me/27696469651?text=$encodeMessage');

    if (await canLaunchUrl(whatsappUrl)) {
      await launchUrl(whatsappUrl, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open WhatsApp')),
        );
      }
    }
  }
}
