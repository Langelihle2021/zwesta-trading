import 'package:flutter/material.dart';
import '../utils/constants.dart';

class StatCard extends StatelessWidget {
  final String title;
  final String value;
  final String? subtitle;
  final IconData icon;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final Function? onTap;

  const StatCard({
    Key? key,
    required this.title,
    required this.value,
    this.subtitle,
    required this.icon,
    this.backgroundColor,
    this.foregroundColor,
    this.onTap,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onTap?.call(),
      child: Card(
        color: backgroundColor ?? Theme.of(context).cardColor,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  Icon(
                    icon,
                    color: foregroundColor ?? AppColors.primaryColor,
                    size: 24,
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: foregroundColor ?? AppColors.dark,
                    ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  subtitle!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class TradeCard extends StatelessWidget {
  final String symbol;
  final String type;
  final double quantity;
  final double entryPrice;
  final double currentPrice;
  final double profit;
  final double profitPercentage;
  final Function? onTap;

  const TradeCard({
    Key? key,
    required this.symbol,
    required this.type,
    required this.quantity,
    required this.entryPrice,
    required this.currentPrice,
    required this.profit,
    required this.profitPercentage,
    this.onTap,
  }) : super(key: key);

  Color get profitColor => profit >= 0 ? AppColors.successColor : AppColors.dangerColor;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onTap?.call(),
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        symbol,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        '${quantity.toStringAsFixed(0)} units @ ${entryPrice.toStringAsFixed(4)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: AppSpacing.xs,
                    ),
                    decoration: BoxDecoration(
                      color: type.toLowerCase() == 'buy'
                          ? AppColors.buyColor.withOpacity(0.1)
                          : AppColors.sellColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      type.toUpperCase(),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: type.toLowerCase() == 'buy'
                            ? AppColors.buyColor
                            : AppColors.sellColor,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Current Price', style: Theme.of(context).textTheme.bodySmall),
                      Text(
                        currentPrice.toStringAsFixed(4),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('Profit/Loss', style: Theme.of(context).textTheme.bodySmall),
                      Text(
                        '${profit >= 0 ? '+' : ''}${profit.toStringAsFixed(2)}',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              color: profitColor,
                            ),
                      ),
                      Text(
                        '${profit >= 0 ? '+' : ''}${profitPercentage.toStringAsFixed(2)}%',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: profitColor,
                            ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class LoadingOverlay extends StatelessWidget {
  final bool isLoading;
  final Widget child;

  const LoadingOverlay({
    Key? key,
    required this.isLoading,
    required this.child,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Stack(
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
}

class CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final bool showBackButton;
  final VoidCallback? onBackPressed;
  final List<Widget>? actions;
  final PreferredSizeWidget? bottom;

  const CustomAppBar({
    Key? key,
    required this.title,
    this.showBackButton = false,
    this.onBackPressed,
    this.actions,
    this.bottom,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      title: Text(title),
      leading: showBackButton
          ? IconButton(
              icon: const Icon(Icons.arrow_back),
              onPressed: onBackPressed ?? () => Navigator.pop(context),
            )
          : null,
      actions: actions,
      bottom: bottom,
    );
  }

  @override
  Size get preferredSize => Size.fromHeight(
    kToolbarHeight + (bottom?.preferredSize.height ?? 0.0),
  );
}

class ErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onDismiss;

  const ErrorBanner({
    Key? key,
    required this.message,
    required this.onDismiss,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      color: AppColors.dangerColor.withOpacity(0.1),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Row(
              children: [
                const Icon(Icons.error, color: AppColors.dangerColor),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    message,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppColors.dangerColor,
                        ),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: onDismiss,
            color: AppColors.dangerColor,
          ),
        ],
      ),
    );
  }
}

class SuccessBanner extends StatelessWidget {
  final String message;
  final VoidCallback onDismiss;

  const SuccessBanner({
    Key? key,
    required this.message,
    required this.onDismiss,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      color: AppColors.successColor.withOpacity(0.1),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Row(
              children: [
                const Icon(Icons.check_circle, color: AppColors.successColor),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    message,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppColors.successColor,
                        ),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: onDismiss,
            color: AppColors.successColor,
          ),
        ],
      ),
    );
  }
}
