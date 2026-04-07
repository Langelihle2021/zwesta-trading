import 'package:flutter/material.dart';

import '../services/activity_log_service.dart';

class ActivityLogScreen extends StatefulWidget {
  const ActivityLogScreen({Key? key}) : super(key: key);

  @override
  State<ActivityLogScreen> createState() => _ActivityLogScreenState();
}

class _ActivityLogScreenState extends State<ActivityLogScreen> {
  List<ActivityLogEntry> _logs = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchLogs();
  }

  Future<void> _fetchLogs() async {
    setState(() { _loading = true; _error = null; });
    try {
      final logs = await ActivityLogService.fetchLogs(context);
      setState(() { _logs = logs; });
    } catch (e) {
      setState(() { _error = 'Failed to load activity logs: $e'; });
    }
    setState(() { _loading = false; });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Activity Log'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchLogs,
            tooltip: 'Refresh logs',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : _logs.isEmpty
                  ? const Center(child: Text('No activity logs found.'))
                  : ListView.builder(
                      itemCount: _logs.length,
                      itemBuilder: (context, i) {
                        final log = _logs[i];
                        return ListTile(
                          leading: const Icon(Icons.event_note, color: Colors.blue),
                          title: Text(log.title),
                          subtitle: Text(log.description),
                          trailing: Text(log.timestamp),
                        );
                      },
                    ),
    );
}
