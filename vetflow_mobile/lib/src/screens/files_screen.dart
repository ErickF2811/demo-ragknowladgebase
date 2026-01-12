import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../app_scope.dart';
import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/status_chip.dart';
import '../widgets/vetflow_card.dart';
import '../widgets/workspace_hero.dart';

class FilesScreen extends StatefulWidget {
  final bool active;

  const FilesScreen({super.key, required this.active});

  @override
  State<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends State<FilesScreen> {
  static const _pollInterval = Duration(seconds: 30);

  ApiClient? _api;
  String? _schema;
  Future<List<FileItem>>? _future;
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
      _future = _loadFiles(api);
    }
    _updateAutoRefresh();
  }

  @override
  void didUpdateWidget(covariant FilesScreen oldWidget) {
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
  Future<List<FileItem>> _loadFiles(ApiClient api) async {
    final items = await api.fetchFiles();
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
      _future = _loadFiles(api);
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
      child: FutureBuilder<List<FileItem>>(
        future: future,
        builder: (context, snapshot) {
          final items = snapshot.data ?? const <FileItem>[];
          final content = <Widget>[
            _buildHeader(items),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Archivos recientes', style: TextStyle(fontWeight: FontWeight.w700)),
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
                child: Text('Sin archivos cargados.'),
              ),
            );
          } else {
            for (final item in items) {
              final createdAt = item.createdAt != null
                  ? formatter.format(item.createdAt!)
                  : 'Sin fecha';
              final tags = item.tags.isNotEmpty ? item.tags.join(', ') : 'Sin tags';
              final status = item.status ?? 'uploaded';
              content.add(
                VetflowCard(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(item.filename, style: Theme.of(context).textTheme.titleMedium),
                            const SizedBox(height: 6),
                            Text('${item.folder ?? 'root'} • $createdAt'),
                            const SizedBox(height: 4),
                            Text(tags),
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

  Widget _buildHeader(List<FileItem> items) {
    final workspaceFuture = _workspaceFuture;
    if (workspaceFuture == null) {
      return WorkspaceHero(
        stats: [
          HeroStat(label: 'Archivos', value: '${items.length}', icon: Icons.folder),
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
          HeroStat(label: 'Archivos', value: '${items.length}', icon: Icons.folder),
          HeroStat(
            label: 'Citas',
            value: '${workspace?.appointmentsCount ?? '--'}',
            icon: Icons.event,
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
