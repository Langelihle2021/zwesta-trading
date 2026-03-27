import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
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
      setState(() { _error = 'Failed to load logs.'; });
    }
    setState(() { _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Activity Log')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView.builder(
                  itemCount: _logs.length,
                  itemBuilder: (context, i) {
                    final log = _logs[i];
                    return ListTile(
                      leading: Icon(Icons.event_note, color: Colors.blue),
                      title: Text(log.title),
                      subtitle: Text(log.description),
                      trailing: Text(log.timestamp),
                    );
                  },
                ),
    );
  }
}
