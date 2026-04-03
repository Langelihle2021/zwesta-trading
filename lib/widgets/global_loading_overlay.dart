import 'package:flutter/material.dart';

class GlobalLoadingOverlay extends StatelessWidget {
  const GlobalLoadingOverlay({required this.isLoading, required this.child, Key? key}) : super(key: key);
  final bool isLoading;
  final Widget child;

  @override
  Widget build(BuildContext context) => Stack(
      children: [
        child,
        if (isLoading)
          Container(
            color: Colors.black.withOpacity(0.3),
            child: const Center(
              child: CircularProgressIndicator(),
            ),
          ),
      ],
    );
}
