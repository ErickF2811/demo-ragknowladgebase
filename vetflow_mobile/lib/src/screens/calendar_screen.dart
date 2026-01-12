import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../app_scope.dart';
import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/status_chip.dart';
import '../widgets/vetflow_card.dart';
import '../widgets/workspace_hero.dart';

class CalendarScreen extends StatefulWidget {
  final bool active;

  const CalendarScreen({super.key, required this.active});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  static const _pollInterval = Duration(seconds: 30);

  ApiClient? _api;
  String? _schema;
  Future<List<Appointment>>? _future;
  Future<Workspace>? _workspaceFuture;
  DateTime? _lastSync;
  bool _syncing = false;
  Timer? _poller;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final scope = AppScope.of(context);
    final api = scope.api;
    final schema = scope.workspace.schema;
    if (_api != api || _schema != schema) {
      _api = api;
      _schema = schema;
      _workspaceFuture = api.fetchWorkspace();
      _future = _loadAppointments(api);
    }
    _updateAutoRefresh();
  }

  @override
  void didUpdateWidget(covariant CalendarScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active != widget.active) {
      _updateAutoRefresh();
      if (widget.active && !oldWidget.active) {
        _refresh();
      }
    }
  }

  @override
  void dispose() {
    _poller?.cancel();
    super.dispose();
  }

  void _updateAutoRefresh() {
    if (!widget.active) {
      _poller?.cancel();
      _poller = null;
      return;
    }
    _poller ??= Timer.periodic(_pollInterval, (_) {
      if (!_syncing) {
        _refresh();
      }
    });
  }
  Future<List<Appointment>> _loadAppointments(ApiClient api) async {
    final items = await api.fetchAppointments();
    if (mounted) {
      setState(() {
        _lastSync = DateTime.now();
      });
    }
    return items;
  }

  Future<void> _refresh() async {
    final api = _api;
    if (api == null) {
      return;
    }
    if (_syncing) {
      return;
    }
    setState(() {
      _syncing = true;
      _workspaceFuture = api.fetchWorkspace();
      _future = _loadAppointments(api);
    });
    try {
      await Future.wait([
        if (_workspaceFuture != null) _workspaceFuture!,
        if (_future != null) _future!,
      ]);
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final future = _future;
    if (future == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final formatter = DateFormat('yyyy-MM-dd HH:mm');
    return RefreshIndicator(
      onRefresh: _refresh,
      child: FutureBuilder<List<Appointment>>(
        future: future,
        builder: (context, snapshot) {
          final items = snapshot.data ?? const <Appointment>[];
          final content = <Widget>[
            _buildHeader(items),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Proximas citas', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ];

          if (snapshot.hasError) {
            content.add(
              VetflowCard(
                child: Text('Error: ${snapshot.error}'),
              ),
            );
          } else if (items.isEmpty) {
            content.add(
              const VetflowCard(
                child: Text('Sin citas registradas.'),
              ),
            );
          } else {
            for (final item in items) {
              final start = item.startTime != null ? formatter.format(item.startTime!) : 'Sin inicio';
              final end = item.endTime != null ? formatter.format(item.endTime!) : 'Sin fin';
              final status = item.status ?? 'programada';
              content.add(
                VetflowCard(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.title,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 6),
                            Text('$start - $end'),
                            if (item.timezone != null && item.timezone!.isNotEmpty)
                              Text('TZ: ${item.timezone}'),
                          ],
                        ),
                      ),
                      StatusChip(label: status, color: statusColor(status)),
                    ],
                  ),
                ),
              );
            }
          }

          if (snapshot.connectionState == ConnectionState.waiting && items.isEmpty) {
            content.add(
              const Padding(
                padding: EdgeInsets.only(top: 40),
                child: Center(child: CircularProgressIndicator()),
              ),
            );
          }

          return ListView(
            padding: const EdgeInsets.only(bottom: 90),
            children: content,
          );
        },
      ),
    );
  }

  Widget _buildHeader(List<Appointment> items) {
    final workspaceFuture = _workspaceFuture;
    if (workspaceFuture == null) {
      return WorkspaceHero(
        stats: [
          HeroStat(label: 'Citas', value: '${items.length}', icon: Icons.event_available),
        ],
        lastSync: _lastSync,
        onRefresh: _refresh,
        loading: _syncing,
        fallbackTitle: AppScope.of(context).workspace.schema,
      );
    }
    return FutureBuilder<Workspace>(
      future: workspaceFuture,
      builder: (context, snapshot) {
        final workspace = snapshot.data;
        final stats = [
          HeroStat(label: 'Citas', value: '${items.length}', icon: Icons.event_available),
          HeroStat(
            label: 'Archivos',
            value: '${workspace?.filesCount ?? '--'}',
            icon: Icons.folder,
          ),
        ];
        return WorkspaceHero(
          workspace: workspace,
          stats: stats,
          lastSync: _lastSync,
          onRefresh: _refresh,
          loading: _syncing || snapshot.connectionState == ConnectionState.waiting,
          fallbackTitle: AppScope.of(context).workspace.schema,
          fallbackSubtitle: snapshot.hasError ? 'Sin datos de workspace' : 'Panel conectado a Vetflow',
        );
      },
    );
  }
}
