import 'dart:async';
import 'dart:convert';

import 'package:clerk_auth/clerk_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persistor que guarda el estado de Clerk en SharedPreferences para
/// mantener la sesión mientras no se cierre manualmente.
class SharedPrefsPersistor implements Persistor {
  SharedPrefsPersistor({this.keyPrefix = 'clerk:'});

  final String keyPrefix;
  SharedPreferences? _prefs;

  String _k(String key) => '$keyPrefix$key';

  @override
  Future<void> initialize() async {
    _prefs ??= await SharedPreferences.getInstance();
  }

  @override
  void terminate() {}

  @override
  FutureOr<T?> read<T>(String key) {
    final raw = _prefs?.getString(_k(key));
    if (raw == null) return null;
    try {
      final decoded = json.decode(raw);
      return decoded as T?;
    } catch (_) {
      return null;
    }
  }

  @override
  FutureOr<void> write<T>(String key, T value) {
    _prefs?.setString(_k(key), json.encode(value));
  }

  @override
  FutureOr<void> delete(String key) {
    _prefs?.remove(_k(key));
  }
}
