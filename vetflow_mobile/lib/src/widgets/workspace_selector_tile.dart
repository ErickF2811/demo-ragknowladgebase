import 'package:flutter/material.dart';

import '../api/models.dart';
import 'status_chip.dart';

class WorkspaceSelectorTile extends StatelessWidget {
  final Workspace workspace;
  final String activeSchema;
  final VoidCallback onSelect;

  const WorkspaceSelectorTile({
    super.key,
    required this.workspace,
    required this.activeSchema,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isActive = workspace.schemaName == activeSchema;
    final name = workspace.name.isNotEmpty ? workspace.name : workspace.schemaName;
    final stats = <String>[];
    if (workspace.appointmentsCount != null) {
      stats.add('${workspace.appointmentsCount} citas');
    }
    if (workspace.filesCount != null) {
      stats.add('${workspace.filesCount} archivos');
    }
    final meta = stats.isNotEmpty ? stats.join(' | ') : workspace.schemaName;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        CircleAvatar(
          radius: 20,
          backgroundColor: theme.colorScheme.primary.withValues(alpha: 0.12),
          backgroundImage: workspace.iconUrl != null && workspace.iconUrl!.isNotEmpty
              ? NetworkImage(workspace.iconUrl!)
              : null,
          child: workspace.iconUrl == null || workspace.iconUrl!.isEmpty
              ? Text(
                  _initialsForName(name),
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.primary,
                    fontWeight: FontWeight.w700,
                  ),
                )
              : null,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: theme.textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(
                meta,
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.outline),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        if (isActive)
          StatusChip(label: 'Activo', color: statusColor('ok'))
        else
          OutlinedButton(
            onPressed: onSelect,
            child: const Text('Cambiar'),
          ),
      ],
    );
  }
}

String _initialsForName(String name) {
  final parts = name.trim().split(RegExp(r'\s+'));
  if (parts.isEmpty || parts.first.isEmpty) {
    return 'WS';
  }
  final first = parts[0];
  final second = parts.length > 1 ? parts[1] : '';
  final initials = (first.isNotEmpty ? first[0] : '') + (second.isNotEmpty ? second[0] : '');
  return initials.isEmpty ? 'WS' : initials.toUpperCase();
}
