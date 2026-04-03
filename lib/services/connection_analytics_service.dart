import 'dart:async';
import '../models/broker_connection_model.dart';

class ConnectionAnalyticsService {
  static final Map<String, List<ConnectionMetric>> _metricsHistory = {};
  static final Map<String, StreamController<List<ConnectionMetric>>>
      _analyticsStreams = {};

  /// Record analytics data point
  static void recordMetric({
    required String accountId,
    required ConnectionMetric metric,
  }) {
    if (!_metricsHistory.containsKey(accountId)) {
      _metricsHistory[accountId] = [];
    }

    _metricsHistory[accountId]!.add(metric);

    // Keep last 500 metrics for analytics
    if (_metricsHistory[accountId]!.length > 500) {
      _metricsHistory[accountId]!.removeAt(0);
    }

    // Notify subscribers
    if (_analyticsStreams.containsKey(accountId)) {
      _analyticsStreams[accountId]?.add(_metricsHistory[accountId]!);
    }
  }

  /// Get latency trends over time
  static List<double> getLatencyTrends(String accountId, {int intervals = 24}) {
    final metrics = _metricsHistory[accountId] ?? [];
    if (metrics.isEmpty) return [];

    final trends = <double>[];
    final metricsPerInterval = (metrics.length / intervals).ceil();

    for (var i = 0; i < intervals; i++) {
      final start = i * metricsPerInterval;
      final end = ((i + 1) * metricsPerInterval).clamp(0, metrics.length);

      if (start < metrics.length) {
        final subset = metrics.sublist(start, end);
        final avgLatency =
            subset.fold<double>(0, (sum, m) => sum + m.latency) / subset.length;
        trends.add(avgLatency);
      }
    }

    return trends;
  }

  /// Get uptime percentage
  static double getUptimePercentage(String accountId) {
    final metrics = _metricsHistory[accountId] ?? [];
    if (metrics.isEmpty) return 0;

    final connected = metrics.where((m) => m.isConnected).length;
    return (connected / metrics.length) * 100;
  }

  /// Get equity growth chart data
  static List<EquityDataPoint> getEquityGrowthData(String accountId) {
    final metrics = _metricsHistory[accountId] ?? [];
    if (metrics.isEmpty) return [];

    return metrics
        .asMap()
        .entries
        .map((e) => EquityDataPoint(
              timeIndex: e.key.toDouble(),
              value: e.value.accountBalance,
              timestamp: e.value.timestamp,
            ))
        .toList();
  }

  /// Get connection health score (0-100)
  static int getConnectionHealthScore(String accountId) {
    final metrics = _metricsHistory[accountId] ?? [];
    if (metrics.isEmpty) return 0;

    var score = 100.0;

    // Reduce score based on disconnections
    final uptime = metrics.where((m) => m.isConnected).length / metrics.length;
    score *= uptime;

    // Reduce score based on high latency (>200ms = bad)
    final avgLatency =
        metrics.fold<double>(0, (sum, m) => sum + m.latency) / metrics.length;
    if (avgLatency > 200) {
      score -= (avgLatency - 200) * 0.1;
    }

    return score.clamp(0, 100).toInt();
  }

  /// Stream analytics updates
  static Stream<List<ConnectionMetric>> getAnalyticsStream(String accountId) {
    if (!_analyticsStreams.containsKey(accountId)) {
      _analyticsStreams[accountId] =
          StreamController<List<ConnectionMetric>>.broadcast();
    }
    return _analyticsStreams[accountId]!.stream;
  }

  /// Get performance metrics summary
  static PerformanceSummary getPerformanceSummary(String accountId) {
    final metrics = _metricsHistory[accountId] ?? [];
    if (metrics.isEmpty) {
      return PerformanceSummary(
        totalConnections: 0,
        successfulConnections: 0,
        averageLatency: 0,
        peakLatency: 0,
        minLatency: 0,
        uptime: 0,
        healthScore: 0,
      );
    }

    final successCount = metrics.where((m) => m.isConnected).length;
    final latencies = metrics.map((m) => m.latency).toList();

    return PerformanceSummary(
      totalConnections: metrics.length,
      successfulConnections: successCount,
      averageLatency:
          latencies.fold<double>(0.0, (a, b) => a + b) / latencies.length,
      peakLatency: latencies.reduce((a, b) => a > b ? a : b),
      minLatency: latencies.reduce((a, b) => a < b ? a : b),
      uptime: (successCount / metrics.length) * 100,
      healthScore: getConnectionHealthScore(accountId),
    );
  }

  /// Export metrics as JSON
  static Map<String, dynamic> exportMetrics(String accountId) {
    final metrics = _metricsHistory[accountId] ?? [];
    final summary = getPerformanceSummary(accountId);

    return {
      'accountId': accountId,
      'exportedAt': DateTime.now().toIso8601String(),
      'summary': {
        'totalConnections': summary.totalConnections,
        'successfulConnections': summary.successfulConnections,
        'averageLatency': summary.averageLatency,
        'uptime': summary.uptime,
        'healthScore': summary.healthScore,
      },
      'metrics': metrics.map((m) => m.toJson()).toList(),
    };
  }

  /// Cleanup
  static void dispose() {
    for (final stream in _analyticsStreams.values) {
      stream.close();
    }
    _analyticsStreams.clear();
    _metricsHistory.clear();
  }
}

class EquityDataPoint {
  EquityDataPoint({
    required this.timeIndex,
    required this.value,
    required this.timestamp,
  });
  final double timeIndex;
  final double value;
  final DateTime timestamp;
}

class PerformanceSummary {
  PerformanceSummary({
    required this.totalConnections,
    required this.successfulConnections,
    required this.averageLatency,
    required this.peakLatency,
    required this.minLatency,
    required this.uptime,
    required this.healthScore,
  });
  final int totalConnections;
  final int successfulConnections;
  final double averageLatency;
  final double peakLatency;
  final double minLatency;
  final double uptime;
  final int healthScore;
}
