import 'package:flutter_test/flutter_test.dart';

import 'package:vetflow_mobile/src/api/api_client.dart';
import 'package:vetflow_mobile/src/api/models.dart';
import 'package:vetflow_mobile/src/app.dart';
import 'package:vetflow_mobile/src/app_scope.dart';
import 'package:vetflow_mobile/src/auth/auth_session.dart';
import 'package:vetflow_mobile/src/config.dart';
import 'package:vetflow_mobile/src/workspace/workspace_session.dart';

class FakeApiClient extends ApiClient {
  FakeApiClient({required super.config});

  @override
  Future<bool> healthCheck() async => true;

  @override
  Future<List<Appointment>> fetchAppointments() async => const <Appointment>[];

  @override
  Future<List<Client>> fetchClients({int limit = 200, String? query}) async =>
      const <Client>[];

  @override
  Future<List<FileItem>> fetchFiles({bool includeExpired = false}) async =>
      const <FileItem>[];

  @override
  Future<Workspace> fetchWorkspace() async {
    return Workspace(
      id: '1',
      name: 'Vetflow Demo',
      schemaName: 'ws_demo',
    );
  }
}

void main() {
  testWidgets('App renders navigation shell', (WidgetTester tester) async {
    final config = AppConfig(
      baseUrl: 'http://localhost:5000',
      schema: 'demo-vetflow',
    );
    final api = FakeApiClient(config: config);
    final auth = AuthSession();
    final workspace = WorkspaceSession(initialSchema: config.schema);

    await tester.pumpWidget(
      AppScope(
        config: config,
        api: api,
        auth: auth,
        workspace: workspace,
        workspaceRevision: workspace.revision,
        child: const VetflowApp(useClerk: false),
      ),
    );

    await tester.pumpAndSettle();
    expect(find.text('Agenda'), findsOneWidget);
  });
}
