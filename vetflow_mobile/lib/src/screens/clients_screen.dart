import 'dart:async';

import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import '../app_scope.dart';
import '../api/api_client.dart';
import '../api/models.dart';
import '../widgets/status_chip.dart';
import '../widgets/vetflow_card.dart';
import '../widgets/workspace_hero.dart';

class ClientsScreen extends StatefulWidget {
  final bool active;

  const ClientsScreen({super.key, required this.active});

  @override
  State<ClientsScreen> createState() => _ClientsScreenState();
}

class _ClientsScreenState extends State<ClientsScreen> {
  static const _pollInterval = Duration(seconds: 30);

  ApiClient? _api;
  String? _schema;
  Future<List<Client>>? _future;
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
      _future = _loadClients(api);
    }
    _updateAutoRefresh();
  }

  @override
  void didUpdateWidget(covariant ClientsScreen oldWidget) {
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
  Future<List<Client>> _loadClients(ApiClient api) async {
    final items = await api.fetchClients();
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
      _future = _loadClients(api);
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
    return RefreshIndicator(
      onRefresh: _refresh,
      child: FutureBuilder<List<Client>>(
        future: future,
        builder: (context, snapshot) {
          final items = snapshot.data ?? const <Client>[];
          final content = <Widget>[
            _buildHeader(items),
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 12, 18, 4),
              child: Text('Clientes activos', style: TextStyle(fontWeight: FontWeight.w700)),
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
                child: Text('Sin clientes registrados.'),
              ),
            );
          } else {
            for (final item in items) {
              final subtitle = [
                '${item.idType}: ${item.idNumber}',
                if (item.phone != null && item.phone!.isNotEmpty) item.phone!,
                if (item.email != null && item.email!.isNotEmpty) item.email!,
              ].where((v) => v.isNotEmpty).join(' - ');
              content.add(
                VetflowCard(
                  onTap: () => _showClientDetail(item),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.fullName,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(color: Theme.of(context).colorScheme.onSurface),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              subtitle,
                              style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
                            ),
                          ],
                        ),
                      ),
                      if (item.blacklisted)
                        const StatusChip(
                          label: 'lista negra',
                          color: Color(0xFFEF4444),
                        ),
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

  Widget _buildHeader(List<Client> items) {
    final workspaceFuture = _workspaceFuture;
    if (workspaceFuture == null) {
      return WorkspaceHero(
        stats: [
          HeroStat(label: 'Clientes', value: '${items.length}', icon: Icons.people_alt, onTap: _refresh),
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
          HeroStat(label: 'Clientes', value: '${items.length}', icon: Icons.people_alt, onTap: _refresh),
          HeroStat(
            label: 'Citas',
            value: '${workspace?.appointmentsCount ?? '--'}',
            icon: Icons.event,
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

  void _showClientDetail(Client client) {
    final nameCtrl = TextEditingController(text: client.fullName);
    final idTypeCtrl = TextEditingController(text: client.idType);
    final idNumberCtrl = TextEditingController(text: client.idNumber);
    final phoneCtrl = TextEditingController(text: client.phone ?? '');
    final emailCtrl = TextEditingController(text: client.email ?? '');
    final addressCtrl = TextEditingController(text: client.address ?? '');
    final notesCtrl = TextEditingController(text: client.notes ?? '');
    bool saving = false;
    String? error;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setModalState) {
          final share = () {
            final buffer = StringBuffer()
              ..writeln(client.fullName)
              ..writeln('${client.idType}: ${client.idNumber}');
            if (client.phone != null && client.phone!.isNotEmpty) {
              buffer.writeln('Tel: ${client.phone}');
            }
            if (client.email != null && client.email!.isNotEmpty) {
              buffer.writeln('Email: ${client.email}');
            }
            if (client.address != null && client.address!.isNotEmpty) {
              buffer.writeln('Direccion: ${client.address}');
            }
            Share.share(buffer.toString());
          };

          final save = () async {
            final api = _api;
            if (api == null) return;
            final name = nameCtrl.text.trim();
            final idType = idTypeCtrl.text.trim();
            final idNumber = idNumberCtrl.text.trim();
            if (name.isEmpty || idType.isEmpty || idNumber.isEmpty) {
              setModalState(() {
                error = 'Nombre, tipo de ID y numero son obligatorios';
              });
              return;
            }
            setModalState(() {
              saving = true;
              error = null;
            });
            try {
              await api.updateClient(client.id, {
                'full_name': name,
                'id_type': idType,
                'id_number': idNumber,
                'phone': phoneCtrl.text.trim(),
                'email': emailCtrl.text.trim(),
                'address': addressCtrl.text.trim(),
                'notes': notesCtrl.text.trim(),
              });
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
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          client.fullName,
                          style: Theme.of(ctx).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.share),
                        tooltip: 'Compartir',
                        onPressed: share,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(labelText: 'Nombre'),
                  ),
                  TextField(
                    controller: idTypeCtrl,
                    decoration: const InputDecoration(labelText: 'Tipo de ID (cedula/pasaporte)'),
                  ),
                  TextField(
                    controller: idNumberCtrl,
                    decoration: const InputDecoration(labelText: 'Numero de ID'),
                  ),
                  TextField(
                    controller: phoneCtrl,
                    decoration: const InputDecoration(labelText: 'Telefono'),
                  ),
                  TextField(
                    controller: emailCtrl,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  TextField(
                    controller: addressCtrl,
                    decoration: const InputDecoration(labelText: 'Direccion'),
                  ),
                  TextField(
                    controller: notesCtrl,
                    decoration: const InputDecoration(labelText: 'Notas'),
                    maxLines: 2,
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 8),
                    Text(error!, style: const TextStyle(color: Colors.red)),
                  ],
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: saving ? null : save,
                      child: saving
                          ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Guardar'),
                    ),
                  ),
                ],
              ),
            ),
          );
        });
      },
    );
  }
}

