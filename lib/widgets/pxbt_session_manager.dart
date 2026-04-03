import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';

class PxbtSessionManager extends StatefulWidget {

  const PxbtSessionManager({
    required this.onStatusChanged, Key? key,
  }) : super(key: key);
  final VoidCallback onStatusChanged;

  @override
  State<PxbtSessionManager> createState() => _PxbtSessionManagerState();
}

class _PxbtSessionManagerState extends State<PxbtSessionManager> {
  bool _isConnected = false;
  bool _isLoading = false;
  bool _isChecking = false;
  List<Map<String, dynamic>> _accounts = [];
  String? _errorMessage;
  DateTime? _lastCheckTime;

  @override
  void initState() {
    super.initState();
    _checkSessionStatus();
  }

  Future<void> _checkSessionStatus() async {
    setState(() => _isChecking = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      if (sessionToken == null || userId == null) {
        setState(() {
          _errorMessage = 'Not authenticated';
          _isChecking = false;
        });
        return;
      }

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/brokers/pxbt/session-status'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
          'X-User-ID': userId,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _isConnected = data['connected'] ?? false;
          _accounts = List<Map<String, dynamic>>.from(data['accounts'] ?? []);
          _errorMessage = null;
          _lastCheckTime = DateTime.now();
          _isChecking = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Failed to check session: ${response.statusCode}';
          _isChecking = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isChecking = false;
      });
    }
  }

  Future<void> _reconnectPxbt(String? credentialId) async {
    setState(() => _isLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      if (sessionToken == null || userId == null) {
        _showError('Not authenticated');
        setState(() => _isLoading = false);
        return;
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/brokers/pxbt/reconnect'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
          'X-User-ID': userId,
        },
        body: credentialId != null ? jsonEncode({'credentialId': credentialId}) : null,
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _showSuccess(data['message'] ?? 'Reconnected to PXBT');
        
        // Refresh status
        await _checkSessionStatus();
        widget.onStatusChanged();
      } else {
        final data = jsonDecode(response.body);
        _showError(data['error'] ?? 'Reconnection failed');
      }
    } catch (e) {
      _showError('Error: $e');
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
    if (_accounts.isEmpty && !_isChecking) {
      return const SizedBox.shrink(); // No PXBT accounts, don't show widget
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: _isConnected ? Colors.green : Colors.orange,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text(
                      'PXBT Connection',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                if (_isChecking)
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                    ),
                  )
                else
                  Text(
                    _isConnected ? '✅ Connected' : '⚠️ Disconnected',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: _isConnected ? Colors.green : Colors.orange,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),

            // Status message
            if (_errorMessage != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: Colors.red.shade700, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _errorMessage!,
                        style: TextStyle(color: Colors.red.shade700, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              )
            else if (!_isConnected && _accounts.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_outlined,
                        color: Colors.orange.shade700, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'PXBT connection lost. Click reconnect to restore.',
                        style: TextStyle(color: Colors.orange.shade700, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              )
            else if (_isConnected && _accounts.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.check_circle_outline,
                        color: Colors.green.shade700, size: 16),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'PXBT is connected and ready for trading',
                        style: TextStyle(color: Colors.green.shade700, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),

            if (_accounts.isNotEmpty) ...[
              const SizedBox(height: 12),

              // Account list
              ..._accounts.map((account) {
                final accountNum = account['accountNumber'] ?? 'N/A';
                final mode = account['mode'] ?? 'DEMO';
                final connected = account['connected'] ?? false;

                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Account #$accountNum',
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                            ),
                            Text(
                              mode,
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.grey.shade700,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (!connected && !_isLoading)
                        SizedBox(
                          height: 32,
                          child: ElevatedButton.icon(
                            onPressed: () => _reconnectPxbt(account['credentialId']),
                            icon: const Icon(Icons.refresh, size: 14),
                            label: const Text('Reconnect'),
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              backgroundColor: Colors.orange,
                              foregroundColor: Colors.white,
                            ),
                          ),
                        )
                        else if (_isLoading)
                          const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                            ),
                          )
                        else
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.green.shade100,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              '✅ Connected',
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.green,
                              ),
                            ),
                          ),
                    ],
                  ),
                );
              }),

              const SizedBox(height: 12),

              // Check status button
              Center(
                child: TextButton.icon(
                  onPressed: _isChecking ? null : _checkSessionStatus,
                  icon: const Icon(Icons.refresh_outlined, size: 16),
                  label: const Text('Check Status'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.blue,
                  ),
                ),
              ),

              if (_lastCheckTime != null)
                Center(
                  child: Text(
                    'Last checked: ${_lastCheckTime!.toLocal().hour}:${_lastCheckTime!.toLocal().minute.toString().padLeft(2, '0')}',
                    style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
