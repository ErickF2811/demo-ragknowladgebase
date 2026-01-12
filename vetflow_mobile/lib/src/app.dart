import 'package:clerk_flutter/clerk_flutter.dart';
import 'package:flutter/material.dart';

import 'auth/auth_gate.dart';
import 'screens/home_screen.dart';
import 'theme/vetflow_theme.dart';

class VetflowApp extends StatelessWidget {
  final bool useClerk;

  const VetflowApp({super.key, required this.useClerk});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Vetflow Mobile',
      debugShowCheckedModeBanner: false,
      theme: VetflowTheme.build(),
      builder: useClerk
          ? (context, child) => ClerkErrorListener(
                child: child ?? const SizedBox.shrink(),
              )
          : null,
      home: useClerk ? const AuthGate() : const HomeScreen(),
    );
  }
}
