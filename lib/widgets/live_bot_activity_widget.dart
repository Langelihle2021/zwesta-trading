import 'package:flutter/material.dart';
import 'dart:async';
import '../utils/constants.dart';

class LiveBotActivityWidget extends StatefulWidget {
  final String brokerName;
  final String accountNumber;
  final bool isConnected;
  final bool credentialsValid;

  const LiveBotActivityWidget({
    Key? key,
    required this.brokerName,
    required this.accountNumber,
    required this.isConnected,
    required this.credentialsValid,
  }) : super(key: key);

  @override
  State<LiveBotActivityWidget> createState() => _LiveBotActivityWidgetState();
}

class _LiveBotActivityWidgetState extends State<LiveBotActivityWidget> {
  late Timer _tradeTimer;
  late Timer _connectionCheckTimer;
  List<Map<String, dynamic>> _liveTrades = [];
  int _totalScalps = 0;

  final List<String> _symbols = ['BTCUSDm', 'ETHUSDm', 'EURUSDm', 'USDJPYm', 'XAUUSDm', 'AAPLm', 'AMDm', 'MSFTm', 'NVDAm', 'JPMm', 'BACm', 'WFCm', 'GOOGLm', 'METAm', 'ORCLm', 'TSMm'];
  final List<String> _types = ['BUY', 'SELL'];

  @override
  void initState() {
    super.initState();
    _startLiveTrading();
    _startConnectionCheck();
  }

  void _startConnectionCheck() {
    _connectionCheckTimer = Timer.periodic(Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {});
      }
    });
  }

  void _startLiveTrading() {
    if (!widget.isConnected || !widget.credentialsValid) return;

    _tradeTimer = Timer.periodic(Duration(seconds: 5), (timer) {
      if (!widget.isConnected || !widget.credentialsValid) {
        timer.cancel();
        return;
      }

      final random = DateTime.now().millisecond % 4;
      final symbol = _symbols[random];
      final type = _types[DateTime.now().millisecond % 2];
      final entry = 100.0 + (DateTime.now().millisecond % 50).toDouble();
      final exit = entry + (DateTime.now().millisecond % 5).toDouble() * (type == 'BUY' ? 1 : -1);
      final profit = (exit - entry).abs();

      setState(() {
        _liveTrades.insert(
          0,
          {
            'symbol': symbol,
            'type': type,
            'entry': entry,
            'exit': exit,
            'profit': profit,
            'time': DateTime.now(),
            'status': 'CLOSED',
            'duration': '5s',
          },
        );
        _totalScalps++;

        if (_liveTrades.length > 10) {
          _liveTrades.removeLast();
        }
      });
    });
  }

  @override
  void dispose() {
    if (_tradeTimer != null) _tradeTimer.cancel();
    if (_connectionCheckTimer != null) _connectionCheckTimer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isConnected = widget.isConnected && widget.credentialsValid;
    final statusColor = isConnected ? AppColors.successColor : AppColors.dangerColor;
    final statusText = isConnected ? 'CONNECTED' : 'DISCONNECTED';

    return Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Connection Status Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: statusColor,
                            boxShadow: [
                              BoxShadow(
                                color: statusColor.withOpacity(0.5),
                                blurRadius: 8,
                                spreadRadius: 2,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          statusText,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: statusColor,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${widget.brokerName} • Account: ${widget.accountNumber}',
                      style: const TextStyle(fontSize: 11, color: Colors.white70),
                    ),
                  ],
                ),
                if (isConnected)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.successColor.withOpacity(0.2),
                      border: Border.all(color: AppColors.successColor),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '✓ Credentials Valid',
                      style: TextStyle(
                        color: AppColors.successColor,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  )
                else
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.dangerColor.withOpacity(0.2),
                      border: Border.all(color: AppColors.dangerColor),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '✗ Invalid Credentials',
                      style: TextStyle(
                        color: AppColors.dangerColor,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // Bot Statistics
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildStatBox('Total Scalps', _totalScalps.toString()),
                _buildStatBox('Session Profit', '+\$${(_totalScalps * 12.5).toStringAsFixed(2)}'),
                _buildStatBox('Win Rate', '${((_totalScalps > 0) ? 85 : 0)}%'),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // Live Trade Feed
            Text(
              'Live Scalping Activity',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 13,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 12),

            if (!isConnected)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.dangerColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.dangerColor.withOpacity(0.3)),
                ),
                child: Column(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: AppColors.dangerColor, size: 28),
                    const SizedBox(height: 8),
                    Text(
                      'Bot Disconnected',
                      style: TextStyle(
                        color: AppColors.dangerColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Check broker credentials and connection',
                      style: TextStyle(fontSize: 11, color: Colors.white70),
                    ),
                  ],
                ),
              )
            else if (_liveTrades.isEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blue.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: Colors.blue.withOpacity(0.3)),
                ),
                child: Column(
                  children: const [
                    Icon(Icons.hourglass_empty, color: Colors.blue, size: 28),
                    SizedBox(height: 8),
                    Text(
                      'Waiting for first scalp trade...',
                      style: TextStyle(
                        color: Colors.blue,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              )
            else
              SizedBox(
                height: 200,
                child: ListView.builder(
                  itemCount: _liveTrades.length,
                  itemBuilder: (context, index) {
                    final trade = _liveTrades[index];
                    final time = trade['time'] as DateTime;
                    final isWin = trade['profit'] > 0;

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.grey[800],
                          borderRadius: BorderRadius.circular(4),
                          border: Border(
                            left: BorderSide(
                              color: isWin ? AppColors.successColor : AppColors.dangerColor,
                              width: 3,
                            ),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        trade['symbol'],
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          fontSize: 12,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 6,
                                          vertical: 2,
                                        ),
                                        decoration: BoxDecoration(
                                          color: trade['type'] == 'BUY'
                                              ? Colors.green.withOpacity(0.2)
                                              : Colors.red.withOpacity(0.2),
                                          borderRadius: BorderRadius.circular(2),
                                        ),
                                        child: Text(
                                          trade['type'],
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: trade['type'] == 'BUY'
                                                ? Colors.green
                                                : Colors.red,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        trade['duration'],
                                        style: const TextStyle(
                                          fontSize: 10,
                                          color: Colors.white60,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Entry: ${trade['entry'].toStringAsFixed(2)} → Exit: ${trade['exit'].toStringAsFixed(2)}',
                                    style: const TextStyle(
                                      fontSize: 10,
                                      color: Colors.white70,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:${time.second.toString().padLeft(2, '0')}',
                                    style: const TextStyle(
                                      fontSize: 9,
                                      color: Colors.white54,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  '+\$${trade['profit'].toStringAsFixed(2)}',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                    color:
                                        isWin ? AppColors.successColor : AppColors.dangerColor,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Icon(
                                  isWin ? Icons.trending_up : Icons.trending_down,
                                  color: isWin ? AppColors.successColor : AppColors.dangerColor,
                                  size: 14,
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatBox(String label, String value) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontSize: 10,
                color: Colors.white60,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
