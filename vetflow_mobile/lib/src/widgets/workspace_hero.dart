import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/models.dart';

class HeroStat {
  final String label;
  final String value;
  final IconData icon;

  const HeroStat({
    required this.label,
    required this.value,
    required this.icon,
  });
}

class WorkspaceHero extends StatelessWidget {
  final Workspace? workspace;
  final List<HeroStat> stats;
  final DateTime? lastSync;
  final VoidCallback? onRefresh;
  final bool loading;
  final String fallbackTitle;
  final String fallbackSubtitle;

  const WorkspaceHero({
    super.key,
    required this.stats,
    this.workspace,
    this.lastSync,
    this.onRefresh,
    this.loading = false,
    this.fallbackTitle = 'Vetflow Workspace',
    this.fallbackSubtitle = 'Panel conectado a Vetflow',
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final accent = _parseColor(workspace?.themeColor, theme.colorScheme.primary);
    final accentStrong = _darken(accent, 0.14);
    final title = workspace?.name.isNotEmpty == true ? workspace!.name : fallbackTitle;
    final subtitle = workspace?.description?.isNotEmpty == true ? workspace!.description! : fallbackSubtitle;
    final owner = workspace?.ownerName;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [accent, accentStrong],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: accent.withValues(alpha: 0.35),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned(
            right: -40,
            top: -30,
            child: _GlowBubble(color: Colors.white.withValues(alpha: 0.08), size: 140),
          ),
          Positioned(
            left: -30,
            bottom: -50,
            child: _GlowBubble(color: Colors.white.withValues(alpha: 0.1), size: 160),
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final vertical = constraints.maxWidth < 520;
              final content = [
                _HeroIdentity(
                  title: title,
                  subtitle: subtitle,
                  owner: owner,
                  iconUrl: workspace?.iconUrl,
                  accent: accent,
                ),
                SizedBox(height: vertical ? 16 : 0, width: vertical ? 0 : 16),
                _HeroMeta(
                  stats: stats,
                  lastSync: lastSync,
                  onRefresh: onRefresh,
                  loading: loading,
                ),
              ];

              if (vertical) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: content,
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: content.first),
                  content[1],
                  content.last,
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _HeroIdentity extends StatelessWidget {
  final String title;
  final String subtitle;
  final String? owner;
  final String? iconUrl;
  final Color accent;

  const _HeroIdentity({
    required this.title,
    required this.subtitle,
    required this.accent,
    this.owner,
    this.iconUrl,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final initials = _initials(title);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _HeroAvatar(iconUrl: iconUrl, initials: initials),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (owner != null && owner!.isNotEmpty)
                _Badge(text: 'Owner: $owner'),
              Text(
                title,
                style: theme.textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.85),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _HeroMeta extends StatelessWidget {
  final List<HeroStat> stats;
  final DateTime? lastSync;
  final VoidCallback? onRefresh;
  final bool loading;

  const _HeroMeta({
    required this.stats,
    this.lastSync,
    this.onRefresh,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    final items = stats
        .where((stat) => stat.value.isNotEmpty)
        .map((stat) => _HeroStatChip(stat: stat))
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Wrap(
          spacing: 10,
          runSpacing: 10,
          alignment: WrapAlignment.end,
          children: items,
        ),
        const SizedBox(height: 12),
        _SyncChip(lastSync: lastSync, loading: loading, onRefresh: onRefresh),
      ],
    );
  }
}

class _HeroAvatar extends StatelessWidget {
  final String? iconUrl;
  final String initials;

  const _HeroAvatar({this.iconUrl, required this.initials});

  @override
  Widget build(BuildContext context) {
    final hasIcon = iconUrl != null && iconUrl!.isNotEmpty;
    return Container(
      width: 64,
      height: 64,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withValues(alpha: 0.35)),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: hasIcon
            ? Image.network(
                iconUrl!,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _InitialsFallback(initials: initials),
              )
            : _InitialsFallback(initials: initials),
      ),
    );
  }
}

class _InitialsFallback extends StatelessWidget {
  final String initials;

  const _InitialsFallback({required this.initials});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        initials,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _HeroStatChip extends StatelessWidget {
  final HeroStat stat;

  const _HeroStatChip({required this.stat});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(stat.icon, size: 18, color: Colors.white),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                stat.value,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
              ),
              Text(
                stat.label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Colors.white.withValues(alpha: 0.85),
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SyncChip extends StatelessWidget {
  final DateTime? lastSync;
  final VoidCallback? onRefresh;
  final bool loading;

  const _SyncChip({
    this.lastSync,
    this.onRefresh,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    final formatter = DateFormat('HH:mm');
    final label = lastSync == null ? 'Sync: --' : 'Sync: ${formatter.format(lastSync!)}';

    return InkWell(
      onTap: loading ? null : onRefresh,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.2),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Colors.white.withValues(alpha: 0.35)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (loading)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            else
              const Icon(Icons.sync, size: 16, color: Colors.white),
            const SizedBox(width: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;

  const _Badge({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
      ),
      child: Text(
        text.toUpperCase(),
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Colors.white.withValues(alpha: 0.9),
              fontWeight: FontWeight.w700,
              letterSpacing: 0.6,
            ),
      ),
    );
  }
}

class _GlowBubble extends StatelessWidget {
  final Color color;
  final double size;

  const _GlowBubble({required this.color, required this.size});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
      ),
    );
  }
}

Color _parseColor(String? raw, Color fallback) {
  if (raw == null || raw.isEmpty) {
    return fallback;
  }
  var value = raw.trim();
  if (value.startsWith('#')) {
    value = value.substring(1);
  }
  if (value.length == 6) {
    value = 'FF$value';
  }
  if (value.length != 8) {
    return fallback;
  }
  final parsed = int.tryParse(value, radix: 16);
  if (parsed == null) {
    return fallback;
  }
  return Color(parsed);
}

Color _darken(Color color, double amount) {
  final hsl = HSLColor.fromColor(color);
  final lightness = (hsl.lightness - amount).clamp(0.0, 1.0);
  return hsl.withLightness(lightness).toColor();
}

String _initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+'));
  if (parts.isEmpty) {
    return 'VF';
  }
  final first = parts.first.isNotEmpty ? parts.first[0] : '';
  final last = parts.length > 1 ? parts.last[0] : '';
  final initials = (first + last).toUpperCase();
  return initials.isEmpty ? 'VF' : initials;
}
