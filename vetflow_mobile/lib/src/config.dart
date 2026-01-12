class AppConfig {
  final String baseUrl;
  final String schema;
  final String? apiKey;
  final String? jwt;
  final String? clerkPublishableKey;

  const AppConfig({
    required this.baseUrl,
    required this.schema,
    this.apiKey,
    this.jwt,
    this.clerkPublishableKey,
  });

  factory AppConfig.fromEnvironment() {
    const baseUrl = String.fromEnvironment(
      'VETFLOW_BASE_URL',
      defaultValue: 'http://localhost:5000',
    );
    const schema = String.fromEnvironment(
      'VETFLOW_SCHEMA',
      defaultValue: '',
    );
    const apiKey = String.fromEnvironment('VETFLOW_API_KEY', defaultValue: '');
    const jwt = String.fromEnvironment('VETFLOW_JWT', defaultValue: '');
    const clerkKey = String.fromEnvironment('CLERK_PUBLISHABLE_KEY', defaultValue: '');
    return AppConfig(
      baseUrl: baseUrl,
      schema: schema,
      apiKey: apiKey.isEmpty ? null : apiKey,
      jwt: jwt.isEmpty ? null : jwt,
      clerkPublishableKey: clerkKey.isEmpty ? null : clerkKey,
    );
  }

  String get normalizedBaseUrl =>
      baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;

  String get apiBaseUrl => '$normalizedBaseUrl/w/$schema/api';

  Uri buildApiUri(String path, [Map<String, String>? queryParameters]) {
    return buildApiUriForSchema(schema, path, queryParameters);
  }

  Uri buildApiUriForSchema(String schema, String path, [Map<String, String>? queryParameters]) {
    final targetSchema = schema.trim().isEmpty ? this.schema : schema.trim();
    final trimmed = path.startsWith('/') ? path.substring(1) : path;
    final url = '$normalizedBaseUrl/w/$targetSchema/api/$trimmed';
    return Uri.parse(url).replace(queryParameters: queryParameters);
  }

  Uri buildHealthUri() {
    return Uri.parse('$normalizedBaseUrl/health');
  }
}
