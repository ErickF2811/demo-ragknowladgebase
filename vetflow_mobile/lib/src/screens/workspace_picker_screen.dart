import 'dart:async';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../app_scope.dart';
import '../widgets/vetflow_card.dart';
import '../widgets/workspace_hero.dart';
import '../widgets/workspace_selector_tile.dart';

class WorkspacePickerScreen extends StatefulWidget {
  const WorkspacePickerScreen({super.key});

  @override
  State<WorkspacePickerScreen> createState() => _WorkspacePickerScreenState();
}

class _WorkspacePickerScreenState extends State<WorkspacePickerScreen> {
  ApiClient? _api;
  Future<List<Workspace>>? _future;
  DateTime? _lastSync;
  bool _syncing = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final api = AppScope.of(context).api;
    if (_api != api) {
      _api = api;
      _future = _loadWorkspaces(api);
    }
  }

  Future<List<Workspace>> _loadWorkspaces(ApiClient api) async {
    final items = await api.fetchWorkspacesRoot();
    if (mounted) {
      setState(() {
        _lastSync = DateTime.now();
      });
    }
    return items;
  }

  Future<void> _refresh() async {
    final api = _api ?? AppScope.of(context).api;
    if (_syncing) {
      return;
    }
    setState(() {
      _syncing = true;
      _future = _loadWorkspaces(api);
    });
    try {
      await _future;
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
        });
      }
    }
  }

  void _selectWorkspace(Workspace workspace) {
    AppScope.of(context).workspace.setSchema(workspace.schemaName);
  }

  @override
  Widget build(BuildContext context) {
    final future = _future;
    if (future == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: FutureBuilder<List<Workspace>>(
            future: future,
            builder: (context, snapshot) {
              final items = snapshot.data ?? const <Workspace>[];
              final content = <Widget>[
                WorkspaceHero(
                  stats: const [],
                  lastSync: _lastSync,
                  onRefresh: _refresh,
                  loading: _syncing,
                  fallbackTitle: 'Selecciona workspace',
                  fallbackSubtitle: 'Elige tu area de trabajo para continuar.',
                ),
                const Padding(
                  padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
                  child: Text('Tus workspaces', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ];

              if (snapshot.hasError) {
                content.add(
                  VetflowCard(
                    child: Text('Error cargando workspaces: ${snapshot.error}'),
                  ),
                );
              } else if (items.isEmpty) {
                content.add(
                  const VetflowCard(
                    child: Text('No hay workspaces disponibles para este usuario.'),
                  ),
                );
              } else {
                for (var i = 0; i < items.length; i++) {
                  content.add(
                    VetflowCard(
                      child: WorkspaceSelectorTile(
                        workspace: items[i],
                        activeSchema: '',
                        onSelect: () => _selectWorkspace(items[i]),
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
        ),
      ),
    );
  }
}
