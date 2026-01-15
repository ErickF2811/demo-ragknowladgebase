import 'package:flutter/foundation.dart';

class AuthSession extends ChangeNotifier {
  AuthSession({String? initialJwt}) : _jwt = initialJwt;

  String? _jwt;
  Future<String?> Function()? _refresher;

  String? get jwt => _jwt;

  bool get isAuthenticated => _jwt != null && _jwt!.isNotEmpty;

  void setRefresher(Future<String?> Function()? refresher) {
    _refresher = refresher;
  }

  Future<String?> token() async {
    if (_refresher != null) {
      final fresh = await _refresher!.call();
      updateJwt(fresh);
      return fresh;
    }
    return _jwt;
  }

  void updateJwt(String? token) {
    if (token == _jwt) {
      return;
    }
    _jwt = token;
    notifyListeners();
  }

  void clear() {
    _refresher = null;
    updateJwt(null);
  }
}
