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
  static const _statusOptions = <Map<String, String>>[
    {'value': 'all', 'label': 'Todas'},
    {'value': 'programada', 'label': 'Programadas'},
    {'value': 'confirmada', 'label': 'Confirmadas'},
    {'value': 'completada', 'label': 'Completadas'},
    {'value': 'cancelada', 'label': 'Canceladas'},
    {'value': 'no_show', 'label': 'No show'},
  ];

  ApiClient? _api;
  String? _schema;
  Future<List<Appointment>>? _future;
  Future<Workspace>? _workspaceFuture;
  DateTime? _lastSync;
  bool _syncing = false;
  Timer? _poller;
  String _activeStatus = 'all';

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

  void _showAppointmentDetail(Appointment item) {
    final formatter = DateFormat('yyyy-MM-dd HH:mm');
    final title = item.title.isNotEmpty ? item.title : '(Sin titulo)';
    String selectedStatus = item.status ?? 'programada';
    bool saving = false;
    String? error;

    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setModalState) {
          final saveStatus = () async {
            final api = _api;
            if (api == null) return;
            setModalState(() {
              saving = true;
              error = null;
            });
            try {
              await api.updateAppointment(item.id, {'status': selectedStatus});
              await _refresh();
              if (mounted) Navigator.of(ctx).pop();
            } catch (e) {
              setModalState(() {
                error = e.toString();
              });
            } finally {
              setModalState(() {
                saving = false;
              });
            }
          };

          return Padding(
            padding: EdgeInsets.only(
              left: 16,
              right: 16,
              top: 12,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: Theme.of(ctx).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                      ),
                    ),
                    StatusChip(label: selectedStatus, color: statusColor(selectedStatus)),
                  ],
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selectedStatus,
                  decoration: const InputDecoration(labelText: 'Estado'),
                  dropdownColor: Theme.of(ctx).colorScheme.surface,
                  style: TextStyle(color: Theme.of(ctx).colorScheme.onSurface),
                  items: _statusOptions
                      .where((opt) => opt['value'] != 'all')
                      .map(
                        (opt) => DropdownMenuItem(
                          value: opt['value']!,
                          child: Text(
                            opt['label']!,
                            style: TextStyle(color: Theme.of(ctx).colorScheme.onSurface),
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (val) {
                    if (val != null) setModalState(() => selectedStatus = val);
                  },
                ),
                const SizedBox(height: 12),
                if (item.description != null && item.description!.trim().isNotEmpty) ...[
                  Text(item.description!.trim(), style: Theme.of(ctx).textTheme.bodyMedium),
                  const SizedBox(height: 12),
                ],
                _detailRow('Inicio', item.startTime != null ? formatter.format(item.startTime!) : 'Sin inicio'),
                _detailRow('Fin', item.endTime != null ? formatter.format(item.endTime!) : 'Sin fin'),
                if (item.timezone != null && item.timezone!.isNotEmpty) _detailRow('Zona', item.timezone!),
                if (item.clientId != null) _detailRow('Cliente ID', '${item.clientId}'),
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Text(error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: saving ? null : saveStatus,
                    child: saving
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Guardar cambios'),
                  ),
                ),
              ],
            ),
          );
        });
      },
    );
  }

  Widget _detailRow(String label, String value) {
    final color = Theme.of(context).colorScheme.onSurface;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(
              label,
              style: TextStyle(fontWeight: FontWeight.w600, color: color),
            ),
          ),
          Expanded(child: Text(value, style: TextStyle(color: color))),
        ],
      ),
    );
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
          final itemsRaw = snapshot.data ?? const <Appointment>[];
          final items = _activeStatus == 'all'
              ? itemsRaw
              : itemsRaw
                  .where((a) => (a.status ?? 'programada').toLowerCase() == _activeStatus)
                  .toList();
          final content = <Widget>[
            _buildHeader(items),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Proximas citas', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
            _buildStatusFilter(),
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
              final title = item.title.isNotEmpty ? item.title : '(Sin titulo)';
              final start = item.startTime != null ? formatter.format(item.startTime!) : 'Sin inicio';
              final end = item.endTime != null ? formatter.format(item.endTime!) : 'Sin fin';
              final status = item.status ?? 'programada';
              content.add(
                VetflowCard(
                  onTap: () => _showAppointmentDetail(item),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              title,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(color: Theme.of(context).colorScheme.onSurface),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              '$start - $end',
                              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                            ),
                            if (item.timezone != null && item.timezone!.isNotEmpty)
                              Text(
                                'TZ: ${item.timezone}',
                                style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                              ),
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
          HeroStat(label: 'Citas', value: '${items.length}', icon: Icons.event_available, onTap: _refresh),
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
          HeroStat(label: 'Citas', value: '${items.length}', icon: Icons.event_available, onTap: _refresh),
          HeroStat(
            label: 'Archivos',
            value: '${workspace?.filesCount ?? '--'}',
            icon: Icons.folder,
            onTap: _refresh,
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

  Widget _buildStatusFilter() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: _statusOptions.map((opt) {
            final active = _activeStatus == opt['value'];
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: ChoiceChip(
                label: Text(opt['label']!),
                selected: active,
                onSelected: (_) {
                  setState(() {
                    _activeStatus = opt['value']!;
                  });
                },
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}
