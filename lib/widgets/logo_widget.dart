import 'package:flutter/material.dart';

class LogoWidget extends StatelessWidget {

  const LogoWidget({
    Key? key,
    this.size = 80,
    this.showText = false,
  }) : super(key: key);
  final double size;
  final bool showText;

  @override
  Widget build(BuildContext context) => Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Display logo - larger and more visible
        ClipRRect(
          borderRadius: BorderRadius.circular(0),
          child: Image.asset(
            'assets/images/logo.jpg',
            width: size,
            height: size,
            fit: BoxFit.cover,
            errorBuilder: (context, error, stackTrace) {
              // Fallback: Show "Z" if image not found
              return Text(
                'Z',
                style: TextStyle(
                  fontSize: size * 0.5,
                  color: Colors.blue.shade900,
                  fontWeight: FontWeight.bold,
                ),
              );
            },
          ),
        ),
        if (showText) ...[
          const SizedBox(height: 20),
          Text(
            'Zwesta Trading System',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ],
    );
}
