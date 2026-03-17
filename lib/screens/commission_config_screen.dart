import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';

class CommissionConfigScreen extends StatefulWidget {
  const CommissionConfigScreen({Key? key}) : super(key: key);

  @override
  State<CommissionConfigScreen> createState() => _CommissionConfigScreenState();
}

class _CommissionConfigScreenState extends State<CommissionConfigScreen> {
  bool _loading = true;
  bool _saving = false;
  String? _error;
  String? _successMsg;
  Map<String, dynamic> _config = {};

  // MT5 rates
  final _devDirectCtrl = TextEditingController();
  final _devReferralCtrl = TextEditingController();
  final _recruiterCtrl = TextEditingController();

  // IG rates
  final _igDevCtrl = TextEditingController();
  final _igRecCtrl = TextEditingController();
  bool _igEnabled = true;

  // Multi-tier
  bool _multiTier = false;
  final _tier2Ctrl = TextEditingController();

  // Preview
  final _previewAmountCtrl = TextEditingController(text: '1000');
  Map<String, dynamic>? _preview;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  @override
  void dispose() {
    _devDirectCtrl.dispose();
    _devReferralCtrl.dispose();
    _recruiterCtrl.dispose();
    _igDevCtrl.dispose();
    _igRecCtrl.dispose();
    _tier2Ctrl.dispose();
    _previewAmountCtrl.dispose();
    super.dispose();
  }

  String get _apiUrl => EnvironmentConfig.apiUrl;

  Future<void> _loadConfig() async {
    setState(() { _loading = true; _error = null; });
    try {
      final resp = await http.get(
        Uri.parse('$_apiUrl/api/admin/commission-config'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        if (data['success'] == true) {
          _config = data['config'] ?? {};
          _devDirectCtrl.text = ((_config['developer_direct_rate'] ?? 0.25) * 100).toStringAsFixed(1);
          _devReferralCtrl.text = ((_config['developer_referral_rate'] ?? 0.20) * 100).toStringAsFixed(1);
          _recruiterCtrl.text = ((_config['recruiter_rate'] ?? 0.05) * 100).toStringAsFixed(1);
          _igDevCtrl.text = ((_config['ig_developer_rate'] ?? 0.20) * 100).toStringAsFixed(1);
          _igRecCtrl.text = ((_config['ig_recruiter_rate'] ?? 0.05) * 100).toStringAsFixed(1);
          _igEnabled = (_config['ig_commission_enabled'] ?? 1) == 1;
          _multiTier = (_config['multi_tier_enabled'] ?? 0) == 1;
          _tier2Ctrl.text = ((_config['tier2_rate'] ?? 0.02) * 100).toStringAsFixed(1);
        }
      }
    } catch (e) {
      _error = e.toString();
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _saveConfig() async {
    setState(() { _saving = true; _error = null; _successMsg = null; });
    try {
      final body = {
        'developer_direct_rate': (double.tryParse(_devDirectCtrl.text) ?? 25) / 100,
        'developer_referral_rate': (double.tryParse(_devReferralCtrl.text) ?? 20) / 100,
        'recruiter_rate': (double.tryParse(_recruiterCtrl.text) ?? 5) / 100,
        'ig_developer_rate': (double.tryParse(_igDevCtrl.text) ?? 20) / 100,
        'ig_recruiter_rate': (double.tryParse(_igRecCtrl.text) ?? 5) / 100,
        'ig_commission_enabled': _igEnabled ? 1 : 0,
        'multi_tier_enabled': _multiTier ? 1 : 0,
        'tier2_rate': (double.tryParse(_tier2Ctrl.text) ?? 2) / 100,
      };

      final resp = await http.post(
        Uri.parse('$_apiUrl/api/admin/commission-config'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(resp.body);
      if (data['success'] == true) {
        _successMsg = 'Rates saved successfully';
        _config = data['config'] ?? _config;
      } else {
        _error = data['error'] ?? 'Save failed';
      }
    } catch (e) {
      _error = e.toString();
    }
    if (mounted) setState(() => _saving = false);
  }

  Future<void> _runPreview({String source = 'MT5', bool hasReferrer = true}) async {
    try {
      final profit = double.tryParse(_previewAmountCtrl.text) ?? 1000;
      final resp = await http.post(
        Uri.parse('$_apiUrl/api/admin/commission-config/preview'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'profit_amount': profit,
          'has_referrer': hasReferrer,
          'source': source,
        }),
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(resp.body);
      if (data['success'] == true && mounted) {
        setState(() => _preview = data);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        title: Row(
          children: const [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Commission Config'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadConfig),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00E5FF)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (_error != null) _msgBox(_error!, Colors.red),
                  if (_successMsg != null) _msgBox(_successMsg!, const Color(0xFF69F0AE)),

                  // MT5 Rates Section
                  _sectionHeader('MT5 / MetaTrader Rates', Icons.candlestick_chart_outlined, const Color(0xFF00E5FF)),
                  const SizedBox(height: 12),
                  _rateRow('Developer (Direct)', _devDirectCtrl, 'No referrer — developer gets this %'),
                  const SizedBox(height: 10),
                  _rateRow('Developer (Referred)', _devReferralCtrl, 'When user has a recruiter'),
                  const SizedBox(height: 10),
                  _rateRow('Recruiter', _recruiterCtrl, 'Referrer earns this % of profits'),

                  const SizedBox(height: 24),

                  // IG Rates Section
                  _sectionHeader('IG Markets Rates', Icons.show_chart, Colors.orangeAccent),
                  const SizedBox(height: 12),
                  _toggleRow('IG Commission Enabled', _igEnabled, (v) => setState(() => _igEnabled = v)),
                  const SizedBox(height: 10),
                  _rateRow('IG Developer Rate', _igDevCtrl, 'Developer % on IG profits'),
                  const SizedBox(height: 10),
                  _rateRow('IG Recruiter Rate', _igRecCtrl, 'Recruiter % on IG profits'),

                  const SizedBox(height: 24),

                  // Multi-tier Section
                  _sectionHeader('Multi-Tier Referrals', Icons.account_tree, const Color(0xFF7C4DFF)),
                  const SizedBox(height: 12),
                  _toggleRow('Enable 2nd-Level Commissions', _multiTier, (v) => setState(() => _multiTier = v)),
                  const SizedBox(height: 10),
                  _rateRow('Tier-2 Rate', _tier2Ctrl, 'Recruiter\'s recruiter earns this %'),

                  const SizedBox(height: 24),

                  // Save Button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      icon: _saving
                          ? const SizedBox(width: 18, height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.save),
                      label: Text(_saving ? 'Saving...' : 'Save Commission Rates',
                          style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 15)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF69F0AE),
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      onPressed: _saving ? null : _saveConfig,
                    ),
                  ),

                  const SizedBox(height: 30),

                  // Preview Section
                  _sectionHeader('Split Preview Calculator', Icons.calculate, const Color(0xFFFFD600)),
                  const SizedBox(height: 12),
                  _buildPreviewSection(),
                ],
              ),
            ),
    );
  }

  Widget _sectionHeader(String title, IconData icon, Color color) {
    return Row(
      children: [
        Icon(icon, color: color, size: 22),
        const SizedBox(width: 10),
        Text(title, style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _rateRow(String label, TextEditingController ctrl, String hint) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                Text(hint, style: GoogleFonts.poppins(color: Colors.white30, fontSize: 10)),
              ],
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 80,
            child: TextField(
              controller: ctrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              textAlign: TextAlign.center,
              style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 18, fontWeight: FontWeight.bold),
              decoration: InputDecoration(
                suffixText: '%',
                suffixStyle: GoogleFonts.poppins(color: Colors.white38, fontSize: 14),
                filled: true,
                fillColor: Colors.white.withOpacity(0.06),
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: Colors.white12),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: const BorderSide(color: Color(0xFF00E5FF), width: 1.5),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _toggleRow(String label, bool value, ValueChanged<bool> onChanged) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(label, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
          ),
          Switch(
            value: value,
            activeColor: const Color(0xFF69F0AE),
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildPreviewSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          TextField(
            controller: _previewAmountCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Profit Amount (\$)',
              labelStyle: GoogleFonts.poppins(color: Colors.white54),
              prefixIcon: const Icon(Icons.attach_money, color: Color(0xFFFFD600)),
              filled: true,
              fillColor: Colors.white.withOpacity(0.06),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.white12),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Color(0xFFFFD600), width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _previewButton('MT5 (Referred)', () => _runPreview(source: 'MT5', hasReferrer: true)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _previewButton('MT5 (Direct)', () => _runPreview(source: 'MT5', hasReferrer: false)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _previewButton('IG (Referred)', () => _runPreview(source: 'IG', hasReferrer: true)),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _previewButton('IG (Direct)', () => _runPreview(source: 'IG', hasReferrer: false)),
              ),
            ],
          ),
          if (_preview != null) ...[
            const SizedBox(height: 16),
            _buildPreviewResult(),
          ],
        ],
      ),
    );
  }

  Widget _previewButton(String label, VoidCallback onTap) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFFFFD600),
        side: const BorderSide(color: Color(0xFFFFD600), width: 0.5),
        padding: const EdgeInsets.symmetric(vertical: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      child: Text(label, style: GoogleFonts.poppins(fontSize: 11, fontWeight: FontWeight.w500)),
    );
  }

  Widget _buildPreviewResult() {
    final p = _preview!;
    final breakdown = p['breakdown'] as Map<String, dynamic>? ?? {};
    final source = p['source'] ?? 'MT5';
    final hasRef = p['has_referrer'] ?? false;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFD600).withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFFD600).withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: source == 'IG' ? Colors.orange.withOpacity(0.2) : const Color(0xFF00E5FF).withOpacity(0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(source, style: GoogleFonts.poppins(
                  color: source == 'IG' ? Colors.orangeAccent : const Color(0xFF00E5FF),
                  fontSize: 11, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: hasRef ? const Color(0xFF7C4DFF).withOpacity(0.2) : Colors.white.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(hasRef ? 'Referred' : 'Direct', style: GoogleFonts.poppins(
                  color: hasRef ? const Color(0xFF7C4DFF) : Colors.white54,
                  fontSize: 11, fontWeight: FontWeight.bold)),
              ),
              const Spacer(),
              Text('Profit: \$${p['profit_amount']}',
                  style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 12),
          ...breakdown.entries.map((e) {
            final role = e.key[0].toUpperCase() + e.key.substring(1);
            final rate = ((e.value['rate'] ?? 0) * 100).toStringAsFixed(1);
            final amount = (e.value['amount'] ?? 0).toStringAsFixed(2);
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('$role ($rate%)',
                      style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13)),
                  Text('\$$amount',
                      style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 14, fontWeight: FontWeight.w600)),
                ],
              ),
            );
          }),
          const Divider(color: Colors.white12, height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Trader Keeps',
                  style: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
              Text('\$${(p['trader_keeps'] ?? 0).toStringAsFixed(2)}',
                  style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 16, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _msgBox(String msg, Color color) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(msg, style: GoogleFonts.poppins(color: color, fontSize: 12)),
    );
  }
}
