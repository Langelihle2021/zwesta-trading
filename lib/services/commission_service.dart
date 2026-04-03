import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';

class Commission {

  Commission({
    required this.commissionId,
    required this.botId,
    required this.amount,
    required this.source,
    required this.status,
    required this.createdAt,
    this.referrerUserId,
    this.referrerName,
  });

  factory Commission.fromJson(Map<String, dynamic> json) => Commission(
      commissionId: json['commission_id'] ?? '',
      botId: json['bot_id'] ?? '',
      amount: (json['amount'] ?? 0).toDouble(),
      source: json['source'] ?? 'trade',
      status: json['status'] ?? 'pending',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toString()),
      referrerUserId: json['referrer_user_id'],
      referrerName: json['referrer_name'],
    );
  final String commissionId;
  final String botId;
  final double amount;
  final String source; // 'trade' or 'referral'
  final String status; // 'pending', 'completed', 'withdrawn'
  final DateTime createdAt;
  final String? referrerUserId; // If commission from referral
  final String? referrerName;
}

class CommissionStats {

  CommissionStats({
    required this.totalEarned,
    required this.totalPending,
    required this.totalWithdrawn,
    required this.tradeCommissions,
    required this.referralCommissions,
  });

  factory CommissionStats.fromJson(Map<String, dynamic> json) => CommissionStats(
      totalEarned: (json['total_earned'] ?? 0).toDouble(),
      totalPending: (json['total_pending'] ?? 0).toDouble(),
      totalWithdrawn: (json['total_withdrawn'] ?? 0).toDouble(),
      tradeCommissions: json['trade_commissions'] ?? 0,
      referralCommissions: json['referral_commissions'] ?? 0,
    );
  final double totalEarned;
  final double totalPending;
  final double totalWithdrawn;
  final int tradeCommissions;
  final int referralCommissions;
}

class CommissionService extends ChangeNotifier {

  CommissionService() {
    _apiUrl = EnvironmentConfig.apiUrl;
    _loadSavedCommissions();
  }
  List<Commission> _commissions = [];
  CommissionStats? _stats;
  bool _isLoading = false;
  String? _errorMessage;
  String? _apiUrl;
  Map<String, dynamic>? _summary;

  List<Commission> get commissions => _commissions;
  CommissionStats? get stats => _stats;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  Map<String, dynamic>? get summary => _summary;
  List<Map<String, dynamic>> get topEarningBots =>
      (_summary?['top_earning_bots'] as List?)?.cast<Map<String, dynamic>>() ?? [];
  double get last30DaysEarned =>
      (_summary?['summary']?['last_30_days_earned'] ?? 0).toDouble();

  /// Fetch commission history and stats
  Future<void> fetchCommissions() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        _errorMessage = 'Not authenticated. Please login again.';
        _isLoading = false;
        notifyListeners();
        return;
      }

      print('💰 Fetching commission data...');

      final response = await http.get(
        Uri.parse('$_apiUrl/api/user/commissions'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        _stats = CommissionStats.fromJson(data['stats']);
        _commissions = (data['commissions'] as List)
            .map((c) => Commission.fromJson(c))
            .toList();

        print('✅ Loaded ${_commissions.length} commissions');
        print('   Total Earned: \$${_stats!.totalEarned}');
        print('   Total Pending: \$${_stats!.totalPending}');
        print('   Trade Commissions: ${_stats!.tradeCommissions}');
        print('   Referral Commissions: ${_stats!.referralCommissions}');

        _saveCommissionsLocal();
      } else {
        _errorMessage = 'Failed to load commissions: ${response.statusCode}';
        print('❌ Error: ${response.statusCode}');
      }

      // Also fetch the detailed summary
      await fetchCommissionSummary();
    } catch (e) {
      _errorMessage = 'Error loading commissions: $e';
      print('❌ Error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Get commissions by source
  List<Commission> getCommissionsBySource(String source) => _commissions.where((c) => c.source == source).toList();

  /// Get commissions by status
  List<Commission> getCommissionsByStatus(String status) => _commissions.where((c) => c.status == status).toList();

  /// Get commissions for specific bot
  List<Commission> getCommissionsForBot(String botId) => _commissions.where((c) => c.botId == botId).toList();

  /// Request commission withdrawal
  Future<bool> requestWithdrawal(double amount) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        _errorMessage = 'Not authenticated';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      print('💳 Requesting withdrawal of \$$amount...');

      final response = await http.post(
        Uri.parse('$_apiUrl/api/user/commission-withdrawal'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({'amount': amount}),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        print('✅ Withdrawal request submitted');
        await fetchCommissions(); // Refresh
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        final data = jsonDecode(response.body);
        _errorMessage = data['error'] ?? 'Failed to request withdrawal';
        print('❌ Error: ${response.statusCode}');
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Error requesting withdrawal: $e';
      print('❌ Error: $e');
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Fetch detailed commission summary (top bots, 30-day earnings)
  Future<void> fetchCommissionSummary() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      if (sessionToken == null) return;

      final response = await http.get(
        Uri.parse('$_apiUrl/api/user/commission-summary'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        _summary = jsonDecode(response.body);
        notifyListeners();
      }
    } catch (e) {
      print('⚠️ Error fetching commission summary: $e');
    }
  }

  /// Get referral commissions specifically
  Future<void> fetchReferralCommissions() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) return;

      print('👥 Fetching referral commission data...');

      final response = await http.get(
        Uri.parse('$_apiUrl/api/user/referral-commissions'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        print('✅ Referral Commissions: ${data['total_referral_commission']}');
        print('   From ${data['active_referrals']} active referrals');
      }
    } catch (e) {
      print('⚠️ Error fetching referral commissions: $e');
    }
  }

  /// Save commissions to local storage
  Future<void> _saveCommissionsLocal() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final commissionsJson = jsonEncode(
        _commissions.map((c) => c.toJson()).toList(),
      );
      await prefs.setString('commissions', commissionsJson);
    } catch (e) {
      print('⚠️ Error saving commissions locally: $e');
    }
  }

  /// Load commissions from local storage
  Future<void> _loadSavedCommissions() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final commissionsJson = prefs.getString('commissions');
      
      if (commissionsJson != null) {
        final commissionsList = (jsonDecode(commissionsJson) as List)
            .map((c) => Commission.fromJson(c))
            .toList();
        _commissions = commissionsList;
      }
    } catch (e) {
      print('⚠️ Error loading saved commissions: $e');
    }
  }
}

extension CommissionJson on Commission {
  Map<String, dynamic> toJson() => {
    'commission_id': commissionId,
    'bot_id': botId,
    'amount': amount,
    'source': source,
    'status': status,
    'created_at': createdAt.toIso8601String(),
    'referrer_user_id': referrerUserId,
    'referrer_name': referrerName,
  };
}
