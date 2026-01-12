import 'package:flutter/foundation.dart';

class AuthSession extends ChangeNotifier {
  AuthSession({String? initialJwt}) : _jwt = initialJwt;

  String? _jwt;

  String? get jwt => _jwt;

  bool get isAuthenticated => _jwt != null && _jwt!.isNotEmpty;

  void updateJwt(String? token) {
    if (token == _jwt) {
      return;
    }
    _jwt = token;
    notifyListeners();
  }

  void clear() => updateJwt(null);
}
