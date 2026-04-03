import 'package:flutter/material.dart';

class _SummaryTile extends StatelessWidget {

  const _SummaryTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    Key? key,
  }) : super(key: key);
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(
      children: [
        CircleAvatar(
          backgroundColor: color.withOpacity(0.15),
          child: Icon(icon, color: color, size: 22),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Colors.white),
        ),
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Colors.white70),
        ),
      ],
    );
}
