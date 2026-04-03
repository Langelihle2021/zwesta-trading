import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';

class TradingModeSwitcher extends StatefulWidget {

  const TradingModeSwitcher({
    required this.currentMode, required this.onModeChanged, Key? key,
    this.isCompact = false,
  }) : super(key: key);
  final String currentMode;
  final Function(String) onModeChanged;
  final bool isCompact;

  @override
  State<TradingModeSwitcher> createState() => _TradingModeSwitcherState();
}

class _TradingModeSwitcherState extends State<TradingModeSwitcher> {
  late String _selectedMode;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _selectedMode = widget.currentMode;
  }

  Future<void> _switchMode(String newMode) async {
    if (_isLoading || newMode == _selectedMode) return;

    setState(() => _isLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      if (sessionToken == null || userId == null) {
        _showError('Not authenticated. Please login again.');
        setState(() => _isLoading = false);
        return;
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/switch-mode'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
          'X-User-ID': userId,
        },
        body: jsonEncode({'mode': newMode}),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        setState(() => _selectedMode = newMode);
        await prefs.setString('trading_mode', newMode);
        
        widget.onModeChanged(newMode);
        
        _showSuccess('Switched to $newMode trading mode');
        print('✅ Trading mode switched to: $newMode');
      } else {
        _showError('Failed to switch mode: ${response.statusCode}');
        print('❌ Error switching mode: ${response.body}');
      }
    } catch (e) {
      _showError('Error: $e');
      print('❌ Error: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isCompact) {
      // Compact pill-style switcher for dashboard header
      return Container(
        decoration: BoxDecoration(
          color: Colors.grey.shade200,
          borderRadius: BorderRadius.circular(20),
        ),
        padding: const EdgeInsets.all(2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildModeButton('DEMO', Colors.green),
            _buildModeButton('LIVE', Colors.red),
          ],
        ),
      );
    }

    // Full-size switcher for dedicated section
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Trading Mode',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildFullModeButton('DEMO', Colors.green),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildFullModeButton('LIVE', Colors.red),
                ),
              ],
            ),
            if (_isLoading)
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildModeButton(String mode, Color color) {
    final isSelected = _selectedMode == mode;
    return GestureDetector(
      onTap: _isLoading ? null : () => _switchMode(mode),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? color : Colors.transparent,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Text(
          mode,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.grey.shade700,
            fontWeight: FontWeight.bold,
            fontSize: 12,
          ),
        ),
      ),
    );
  }

  Widget _buildFullModeButton(String mode, Color color) {
    final isSelected = _selectedMode == mode;
    return GestureDetector(
      onTap: _isLoading ? null : () => _switchMode(mode),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.2) : Colors.grey.shade100,
          border: Border.all(
            color: isSelected ? color : Colors.grey.shade300,
            width: isSelected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                mode == 'DEMO' ? Icons.school : Icons.trending_up,
                color: isSelected ? color : Colors.grey.shade600,
              ),
              const SizedBox(height: 4),
              Text(
                mode,
                style: TextStyle(
                  color: isSelected ? color : Colors.grey.shade600,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
