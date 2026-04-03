import 'package:flutter/material.dart';

class GlobalErrorBanner extends StatelessWidget {

  const GlobalErrorBanner({
    required this.errorMessage, Key? key,
    this.onRetry,
    this.show = false,
  }) : super(key: key);
  final String? errorMessage;
  final VoidCallback? onRetry;
  final bool show;

  @override
  Widget build(BuildContext context) {
    if (!show || errorMessage == null || errorMessage!.isEmpty) return const SizedBox.shrink();
    return MaterialBanner(
      content: Text(errorMessage!, style: const TextStyle(color: Colors.white)),
      backgroundColor: Colors.red[800],
      actions: [
        if (onRetry != null)
          TextButton(
            onPressed: onRetry,
            child: const Text('Retry', style: TextStyle(color: Colors.white)),
          ),
        TextButton(
          onPressed: () => ScaffoldMessenger.of(context).hideCurrentMaterialBanner(),
          child: const Text('Dismiss', style: TextStyle(color: Colors.white)),
        ),
      ],
    );
  }
}
