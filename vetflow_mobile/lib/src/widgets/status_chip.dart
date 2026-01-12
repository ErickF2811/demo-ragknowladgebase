import 'package:flutter/material.dart';

class StatusChip extends StatelessWidget {
  final String label;
  final Color color;

  const StatusChip({
    super.key,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

Color statusColor(String raw) {
  final value = raw.toLowerCase().trim();
  switch (value) {
    case 'ok':
      return const Color(0xFF16A34A);
    case 'no responde':
    case 'unavailable':
      return const Color(0xFFF97316);
    case 'error':
    case 'failed':
      return const Color(0xFFEF4444);
    case 'confirmada':
    case 'confirmed':
      return const Color(0xFF0EA5A4);
    case 'completada':
    case 'completed':
      return const Color(0xFF16A34A);
    case 'cancelada':
    case 'cancelled':
    case 'canceled':
      return const Color(0xFFEF4444);
    case 'no_show':
    case 'no-show':
      return const Color(0xFFF97316);
    case 'processing':
      return const Color(0xFF3B82F6);
    case 'processed':
    case 'done':
      return const Color(0xFF22C55E);
    case 'deleting':
      return const Color(0xFFF59E0B);
    case 'deleted':
    case 'expired':
      return const Color(0xFF6B7280);
    default:
      return const Color(0xFF64748B);
  }
}
