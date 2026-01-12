import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config.dart';
import 'models.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  final AppConfig config;
  final String? Function()? jwtProvider;
  final String Function()? schemaProvider;
  final http.Client _client;

  ApiClient({
    required this.config,
    this.jwtProvider,
    this.schemaProvider,
    http.Client? client,
  })
      : _client = client ?? http.Client();

  void _log(String message) {
    if (kDebugMode) {
      debugPrint('[ApiClient] $message');
    }
  }

  String _truncate(String value, {int limit = 300}) {
    if (value.length <= limit) {
      return value;
    }
    return '${value.substring(0, limit)}...';
  }

  Map<String, String> _headers({bool json = true}) {
    final headers = <String, String>{};
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
    final apiKey = config.apiKey;
    final jwt = jwtProvider?.call() ?? config.jwt;
    if (jwt != null && jwt.isNotEmpty) {
      headers['Authorization'] = 'Bearer $jwt';
      return headers;
    }
    if (apiKey != null && apiKey.isNotEmpty) {
      headers['X-API-Key'] = apiKey;
    }
    return headers;
  }

  Uri _buildApiUri(String path, [Map<String, String>? queryParameters]) {
    final provider = schemaProvider;
    final schema = provider == null ? null : provider().trim();
    if (schema != null && schema.isNotEmpty) {
      return config.buildApiUriForSchema(schema, path, queryParameters);
    }
    final fallback = config.schema.trim();
    if (fallback.isNotEmpty) {
      return config.buildApiUriForSchema(fallback, path, queryParameters);
    }
    throw StateError('Workspace schema missing for API request.');
  }

  Uri _buildRootUri(String path, [Map<String, String>? queryParameters]) {
    final trimmed = path.startsWith('/') ? path.substring(1) : path;
    final url = '${config.normalizedBaseUrl}/$trimmed';
    return Uri.parse(url).replace(queryParameters: queryParameters);
  }

  Future<dynamic> _getJson(Uri uri) async {
    _log('GET $uri');
    try {
      final response = await _client.get(uri, headers: _headers(json: false));
      final body = utf8.decode(response.bodyBytes);
      _log('GET $uri -> ${response.statusCode}');
      if (response.statusCode < 200 || response.statusCode >= 300) {
        _log('GET $uri error body=${_truncate(body)}');
        throw ApiException(response.statusCode, body.isEmpty ? 'Request failed' : body);
      }
      if (body.isEmpty) {
        return null;
      }
      return jsonDecode(body);
    } catch (error) {
      _log('GET $uri failed: $error');
      rethrow;
    }
  }

  Future<bool> healthCheck() async {
    final uri = config.buildHealthUri();
    _log('GET $uri');
    try {
      final response = await _client.get(uri);
      _log('GET $uri -> ${response.statusCode}');
      return response.statusCode == 200;
    } catch (error) {
      _log('GET $uri failed: $error');
      rethrow;
    }
  }

  Future<List<Appointment>> fetchAppointments() async {
    final data = await _getJson(_buildApiUri('calendar'));
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map(Appointment.fromJson)
          .toList();
    }
    throw const FormatException('Unexpected response for calendar list.');
  }

  Future<List<Client>> fetchClients({int limit = 200, String? query}) async {
    final queryParams = <String, String>{'limit': '$limit'};
    if (query != null && query.isNotEmpty) {
      queryParams['q'] = query;
    }
    final data = await _getJson(_buildApiUri('clientes', queryParams));
    if (data is Map<String, dynamic>) {
      final list = data['clients'];
      if (list is List) {
        return list
            .whereType<Map<String, dynamic>>()
            .map(Client.fromJson)
            .toList();
      }
      return const <Client>[];
    }
    throw const FormatException('Unexpected response for client list.');
  }

  Future<List<FileItem>> fetchFiles({bool includeExpired = false}) async {
    final data = await _getJson(
      _buildApiUri(
        'files',
        {'include_expired': includeExpired ? '1' : '0'},
      ),
    );
    if (data is Map<String, dynamic>) {
      final list = data['files'];
      if (list is List) {
        return list
            .whereType<Map<String, dynamic>>()
            .map(FileItem.fromJson)
            .toList();
      }
      return const <FileItem>[];
    }
    throw const FormatException('Unexpected response for file list.');
  }

  Future<Workspace> fetchWorkspace() async {
    final data = await _getJson(_buildApiUri('workspace'));
    if (data is Map<String, dynamic>) {
      final workspace = data['workspace'];
      if (workspace is Map<String, dynamic>) {
        return Workspace.fromJson(workspace);
      }
    }
    throw const FormatException('Unexpected response for workspace.');
  }

  Future<List<Workspace>> fetchWorkspaces() async {
    final data = await _getJson(_buildApiUri('workspaces'));
    if (data is Map<String, dynamic>) {
      final list = data['workspaces'];
      if (list is List) {
        return list
            .whereType<Map<String, dynamic>>()
            .map(Workspace.fromJson)
            .toList();
      }
      return const <Workspace>[];
    }
    throw const FormatException('Unexpected response for workspaces.');
  }

  Future<List<Workspace>> fetchWorkspacesRoot() async {
    final data = await _getJson(_buildRootUri('api/workspaces'));
    if (data is Map<String, dynamic>) {
      final list = data['workspaces'];
      if (list is List) {
        return list
            .whereType<Map<String, dynamic>>()
            .map(Workspace.fromJson)
            .toList();
      }
      return const <Workspace>[];
    }
    throw const FormatException('Unexpected response for workspaces.');
  }
}
