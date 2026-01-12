import 'package:clerk_auth/clerk_auth.dart' as clerk;
import 'package:clerk_flutter/clerk_flutter.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'src/api/api_client.dart';
import 'src/app.dart';
import 'src/app_scope.dart';
import 'src/auth/auth_session.dart';
import 'src/auth/web_clerk_cache.dart';
import 'src/config.dart';
import 'src/workspace/workspace_session.dart';

void main() {
  final config = AppConfig.fromEnvironment();
  runApp(VetflowRoot(config: config));
}

class VetflowRoot extends StatefulWidget {
  final AppConfig config;

  const VetflowRoot({super.key, required this.config});

  @override
  State<VetflowRoot> createState() => _VetflowRootState();
}

class _VetflowRootState extends State<VetflowRoot> {
  late final AuthSession _authSession = AuthSession(initialJwt: widget.config.jwt);
  late final WorkspaceSession _workspaceSession =
      WorkspaceSession(initialSchema: widget.config.schema.trim());
  late final ApiClient _apiClient = ApiClient(
    config: widget.config,
    jwtProvider: () => _authSession.jwt,
    schemaProvider: () => _workspaceSession.schema,
  );

  @override
  Widget build(BuildContext context) {
    final app = AnimatedBuilder(
      animation: _workspaceSession,
      builder: (context, _) {
        return AppScope(
          config: widget.config,
          api: _apiClient,
          auth: _authSession,
          workspace: _workspaceSession,
          workspaceRevision: _workspaceSession.revision,
          child: VetflowApp(useClerk: widget.config.clerkPublishableKey != null),
        );
      },
    );

    final clerkKey = widget.config.clerkPublishableKey;
    if (clerkKey == null || clerkKey.isEmpty) {
      return app;
    }

    const flags = ClerkSdkFlags(clearCookiesOnSignOut: true);
    final clerkConfig = kIsWeb
        ? ClerkAuthConfig(
            publishableKey: clerkKey,
            persistor: clerk.Persistor.none,
            fileCache: NoopClerkFileCache(),
            flags: flags,
          )
        : ClerkAuthConfig(
            publishableKey: clerkKey,
            flags: flags,
          );

    return ClerkAuth(
      config: clerkConfig,
      child: app,
    );
  }
}
