import 'dart:async';

import 'package:clerk_flutter/clerk_flutter.dart';
import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/status_chip.dart';
import '../widgets/vetflow_card.dart';
import '../widgets/workspace_hero.dart';
import '../widgets/workspace_selector_tile.dart';

class SettingsScreen extends StatefulWidget {
  final bool active;

  const SettingsScreen({super.key, required this.active});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _pollInterval = Duration(seconds: 45);

  String? _healthStatus;
  bool _checking = false;
  ApiClient? _api;
  String? _schema;
  Future<Workspace>? _workspaceFuture;
  Future<List<Workspace>>? _workspacesFuture;
  DateTime? _lastSync;
  bool _syncing = false;
  Timer? _poller;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final scope = AppScope.of(context);
    final api = scope.api;
    final schema = scope.workspace.schema;
    final apiChanged = _api != api;
    final schemaChanged = _schema != schema;
    if (apiChanged) {
      _api = api;
      _workspacesFuture = _loadWorkspaces(api, schema);
    }
    if (apiChanged || schemaChanged) {
      _schema = schema;
      _workspaceFuture = schema.trim().isEmpty ? null : _loadWorkspace(api);
    }
    _updateAutoRefresh();
  }

  @override
  void didUpdateWidget(covariant SettingsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active != widget.active) {
      _updateAutoRefresh();
      if (widget.active && !oldWidget.active) {
        _refreshWorkspace();
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
        _refreshWorkspace();
      }
    });
  }

  Future<void> _checkHealth() async {
    setState(() {
      _checking = true;
      _healthStatus = null;
    });
    final api = _api ?? AppScope.of(context).api;
    try {
      final ok = await api.healthCheck();
      setState(() {
        _healthStatus = ok ? 'ok' : 'no responde';
      });
    } catch (error) {
      setState(() {
        _healthStatus = 'error';
      });
    } finally {
      setState(() {
        _checking = false;
      });
    }
  }

  Future<Workspace> _loadWorkspace(ApiClient api) async {
    final workspace = await api.fetchWorkspace();
    if (mounted) {
      setState(() {
        _lastSync = DateTime.now();
      });
    }
    return workspace;
  }

  Future<void> _refreshWorkspace() async {
    final api = _api ?? AppScope.of(context).api;
    _api ??= api;
    if (AppScope.of(context).workspace.schema.trim().isEmpty) {
      return;
    }
    if (_syncing) {
      return;
    }
    setState(() {
      _syncing = true;
      _workspaceFuture = _loadWorkspace(api);
    });
    try {
      await _workspaceFuture;
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
        });
      }
    }
  }

  Future<void> _selectWorkspace(Workspace workspace) async {
    final scope = AppScope.of(context);
    scope.workspace.setSchema(workspace.schemaName);
  }

  Future<List<Workspace>> _loadWorkspaces(ApiClient api, String schema) {
    if (schema.trim().isEmpty) {
      return api.fetchWorkspacesRoot();
    }
    return api.fetchWorkspaces();
  }

  @override
  Widget build(BuildContext context) {
    final scope = AppScope.of(context);
    final apiKeyLabel = scope.config.apiKey == null ? 'No configurada' : 'Configurada';
    final jwtLabel = scope.auth.jwt == null ? 'No configurado' : 'Configurado';
    final hasClerk = scope.config.clerkPublishableKey != null;
    final hasSchema = scope.workspace.schema.trim().isNotEmpty;
    final fallbackTitle = hasSchema ? scope.workspace.schema : 'Sin workspace';
    final fallbackSubtitle =
        hasSchema ? 'Panel conectado a Vetflow' : 'Selecciona un workspace para continuar.';

    return FutureBuilder<Workspace>(
      future: _workspaceFuture,
      builder: (context, snapshot) {
        final workspace = snapshot.data;
        final stats = [
          HeroStat(
            label: 'Archivos',
            value: '${workspace?.filesCount ?? '--'}',
            icon: Icons.folder,
          ),
          HeroStat(
            label: 'Citas',
            value: '${workspace?.appointmentsCount ?? '--'}',
            icon: Icons.event,
          ),
        ];

        return ListView(
          padding: const EdgeInsets.only(bottom: 90),
          children: [
            WorkspaceHero(
              workspace: workspace,
              stats: stats,
              lastSync: _lastSync,
              onRefresh: _refreshWorkspace,
              loading: _syncing || snapshot.connectionState == ConnectionState.waiting,
              fallbackTitle: fallbackTitle,
              fallbackSubtitle: snapshot.hasError ? 'Sin datos de workspace' : fallbackSubtitle,
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Conexion', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
            VetflowCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Base URL', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(scope.config.normalizedBaseUrl),
                  const SizedBox(height: 12),
                  const Text('Workspace schema', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(hasSchema ? scope.workspace.schema : 'No seleccionado'),
                  const SizedBox(height: 12),
                  const Text('API Key', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(apiKeyLabel),
                  const SizedBox(height: 12),
                  const Text('JWT', style: TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(jwtLabel),
                ],
              ),
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Workspaces', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
            VetflowCard(
              child: FutureBuilder<List<Workspace>>(
                future: _workspacesFuture,
                builder: (context, listSnapshot) {
                  final items = listSnapshot.data ?? const <Workspace>[];
                  if (listSnapshot.hasError) {
                    return Text('Error cargando workspaces: ${listSnapshot.error}');
                  }
                  if (listSnapshot.connectionState == ConnectionState.waiting && items.isEmpty) {
                    return Row(
                      children: const [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        SizedBox(width: 12),
                        Text('Cargando workspaces...'),
                      ],
                    );
                  }
                  if (items.isEmpty) {
                    return const Text('No hay workspaces disponibles para este usuario.');
                  }
                  final activeSchema = scope.workspace.schema;
                  return Column(
                    children: [
                      for (var i = 0; i < items.length; i++) ...[
                        WorkspaceSelectorTile(
                          workspace: items[i],
                          activeSchema: activeSchema,
                          onSelect: () => _selectWorkspace(items[i]),
                        ),
                        if (i != items.length - 1) const Divider(height: 24),
                      ],
                    ],
                  );
                },
              ),
            ),
            if (hasClerk) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
                child: Text('Sesion', style: TextStyle(fontWeight: FontWeight.w700)),
              ),
              VetflowCard(
                child: ElevatedButton.icon(
                  onPressed: () async {
                    await ClerkAuth.of(context, listen: false).signOut();
                    scope.auth.clear();
                    scope.workspace.clear();
                  },
                  icon: const Icon(Icons.logout),
                  label: const Text('Cerrar sesion'),
                ),
              ),
            ],
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Diagnostico', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
            VetflowCard(
              child: Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _checking ? null : _checkHealth,
                      icon: const Icon(Icons.health_and_safety),
                      label: Text(_checking ? 'Verificando...' : 'Probar /health'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  if (_healthStatus != null)
                    StatusChip(
                      label: _healthStatus!,
                      color: statusColor(_healthStatus!),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
