import 'dart:async';

import 'package:clerk_flutter/clerk_flutter.dart';
import 'package:flutter/material.dart';

import '../app_scope.dart';
import '../screens/home_screen.dart';
import 'auth_session.dart';

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final scope = AppScope.of(context);
    final authSession = scope.auth;
    authSession.setRefresher(() async => null);
    return ClerkAuthBuilder(
      signedInBuilder: (context, authState) {
        return ClerkTokenSync(
          authState: authState,
          session: authSession,
          child: const HomeScreen(),
        );
      },
      signedOutBuilder: (context, authState) {
        if (authSession.isAuthenticated) {
          authSession.clear();
        }
        scope.workspace.clear();
        return const SignInScreen();
      },
    );
  }
}

class ClerkTokenSync extends StatefulWidget {
  final ClerkAuthState authState;
  final AuthSession session;
  final Widget child;

  const ClerkTokenSync({
    super.key,
    required this.authState,
    required this.session,
    required this.child,
  });

  @override
  State<ClerkTokenSync> createState() => _ClerkTokenSyncState();
}

class _ClerkTokenSyncState extends State<ClerkTokenSync> {
  StreamSubscription? _sub;

  @override
  void initState() {
    super.initState();
    widget.session.setRefresher(() => _fetchToken(widget.authState));
    _syncToken();
    _sub = widget.authState.sessionTokenStream.listen((token) {
      widget.session.updateJwt(token.jwt);
    });
  }

  @override
  void didUpdateWidget(covariant ClerkTokenSync oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.authState != widget.authState) {
      _sub?.cancel();
      widget.session.setRefresher(() => _fetchToken(widget.authState));
      _syncToken();
      _sub = widget.authState.sessionTokenStream.listen((token) {
        widget.session.updateJwt(token.jwt);
      });
    }
  }

  Future<void> _syncToken() async {
    await _fetchToken(widget.authState);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;

  Future<String?> _fetchToken(ClerkAuthState state) async {
    try {
      final token = await state.sessionToken();
      widget.session.updateJwt(token.jwt);
      return token.jwt;
    } catch (_) {
      // The auth state will surface errors through Clerk error streams.
      return widget.session.jwt;
    }
  }
}

class SignInScreen extends StatelessWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: const ClerkAuthentication(),
          ),
        ),
      ),
    );
  }
}
