import 'package:flutter/widgets.dart';

import 'auth/auth_session.dart';
import 'api/api_client.dart';
import 'config.dart';
import 'workspace/workspace_session.dart';

class AppScope extends InheritedWidget {
  final AppConfig config;
  final ApiClient api;
  final AuthSession auth;
  final WorkspaceSession workspace;
  final int workspaceRevision;

  const AppScope({
    super.key,
    required this.config,
    required this.api,
    required this.auth,
    required this.workspace,
    required this.workspaceRevision,
    required super.child,
  });

  static AppScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope not found in context');
    return scope!;
  }

  @override
  bool updateShouldNotify(AppScope oldWidget) {
    return config != oldWidget.config ||
        api != oldWidget.api ||
        auth != oldWidget.auth ||
        workspace != oldWidget.workspace ||
        workspaceRevision != oldWidget.workspaceRevision;
  }
}
