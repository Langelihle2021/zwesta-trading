import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

class BackendStatusIndicator extends StatefulWidget {
  const BackendStatusIndicator({Key? key, this.size = 16}) : super(key: key);
  final double size;

  @override
  State<BackendStatusIndicator> createState() => _BackendStatusIndicatorState();
}

class _BackendStatusIndicatorState extends State<BackendStatusIndicator> {
  bool? _isOnline;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _checkBackend();
  }

  Future<void> _checkBackend() async {
    setState(() => _loading = true);
    try {
      final response = await http.get(Uri.parse('${EnvironmentConfig.apiUrl}/api/health')).timeout(const Duration(seconds: 5));
      setState(() {
        _isOnline = response.statusCode == 200;
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _isOnline = false;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    Color color;
    String tooltip;
    if (_loading) {
      color = Colors.grey;
      tooltip = 'Checking backend...';
    } else if (_isOnline == true) {
      color = Colors.green;
      tooltip = 'Backend online';
    } else {
      color = Colors.red;
      tooltip = 'Backend offline';
    }
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: _checkBackend,
        child: Icon(Icons.circle, color: color, size: widget.size),
      ),
    );
  }
}
