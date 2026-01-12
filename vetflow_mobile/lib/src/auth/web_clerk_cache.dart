import 'dart:io';

// ignore: implementation_imports
import 'package:clerk_flutter/src/utils/clerk_file_cache.dart';

class NoopClerkFileCache extends ClerkFileCache {
  NoopClerkFileCache();

  @override
  Stream<File> stream(
    Uri uri, {
    Duration ttl = ClerkFileCache.defaultTTL,
    Map<String, String>? headers,
  }) {
    return const Stream<File>.empty();
  }
}
