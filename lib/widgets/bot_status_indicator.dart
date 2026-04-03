import 'package:flutter/material.dart';

/// Animated indicator showing bot running status with pulsing effect
class BotStatusIndicator extends StatefulWidget {

  const BotStatusIndicator({
    Key? key,
    this.isRunning = false,
    this.isConnected = false,
    this.status = 'Idle',
  }) : super(key: key);
  final bool isRunning;
  final bool isConnected;
  final String status;

  @override
  State<BotStatusIndicator> createState() => _BotStatusIndicatorState();
}

class _BotStatusIndicatorState extends State<BotStatusIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _opacityAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _opacityAnimation = Tween<double>(begin: 0.3, end: 1).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    if (widget.isRunning) {
      _animationController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(BotStatusIndicator oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isRunning && !oldWidget.isRunning) {
      _animationController.repeat(reverse: true);
    } else if (!widget.isRunning && oldWidget.isRunning) {
      _animationController.stop();
      _animationController.reset();
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Color get _statusColor {
    if (!widget.isConnected) return Colors.grey;
    if (widget.isRunning) return Colors.green;
    return Colors.orange;
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: _opacityAnimation,
      builder: (context, child) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Status Indicator Light
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _statusColor.withOpacity(
                  widget.isRunning ? _opacityAnimation.value : 1.0,
                ),
                boxShadow: widget.isRunning
                    ? [
                        BoxShadow(
                          color: _statusColor.withOpacity(0.6),
                          blurRadius: 8,
                          spreadRadius: 2,
                        )
                      ]
                    : null,
              ),
            ),
            const SizedBox(width: 8),
            // Status Text
            Text(
              widget.status,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: _statusColor,
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ],
        ),
    );
}

/// Compact running indicator badge for bot lists
class BotRunningBadge extends StatefulWidget {

  const BotRunningBadge({
    Key? key,
    this.isRunning = false,
  }) : super(key: key);
  final bool isRunning;

  @override
  State<BotRunningBadge> createState() => _BotRunningBadgeState();
}

class _BotRunningBadgeState extends State<BotRunningBadge>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    if (widget.isRunning) {
      _animationController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(BotRunningBadge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isRunning && !oldWidget.isRunning) {
      _animationController.repeat(reverse: true);
    } else if (!widget.isRunning && oldWidget.isRunning) {
      _animationController.stop();
      _animationController.reset();
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.isRunning) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.orange,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Text(
          'Stopped',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
            fontSize: 11,
          ),
        ),
      );
    }

    return AnimatedBuilder(
      animation: _scaleAnimation,
      builder: (context, child) => Transform.scale(
          scale: _scaleAnimation.value,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.green,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.green.withOpacity(0.5),
                  blurRadius: 8,
                  spreadRadius: 2,
                )
              ],
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.play_arrow, size: 12, color: Colors.white),
                SizedBox(width: 4),
                Text(
                  'Running',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ),
    );
  }
}
