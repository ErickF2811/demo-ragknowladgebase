import 'package:flutter/foundation.dart';

class WorkspaceSession extends ChangeNotifier {
  WorkspaceSession({required String initialSchema}) : _schema = initialSchema;

  String _schema;
  int _revision = 0;

  String get schema => _schema;
  int get revision => _revision;

  bool setSchema(String schema) {
    final trimmed = schema.trim();
    if (trimmed.isEmpty || trimmed == _schema) {
      return false;
    }
    _schema = trimmed;
    _revision += 1;
    notifyListeners();
    return true;
  }

  bool clear() {
    if (_schema.isEmpty) {
      return false;
    }
    _schema = '';
    _revision += 1;
    notifyListeners();
    return true;
  }
}
