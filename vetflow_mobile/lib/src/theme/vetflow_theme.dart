import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class VetflowTheme {
  static const Color primary = Color(0xFF1B9E57);
  static const Color primaryStrong = Color(0xFF13713E);
  static const Color background = Color(0xFFF2F6F4);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceAlt = Color(0xFFF7FBF8);
  static const Color border = Color(0xFFDDE7E1);
  static const Color textMain = Color(0xFF18211B);
  static const Color textMuted = Color(0xFF6B7280);

  static ThemeData build() {
    final base = ThemeData.light(useMaterial3: true);
    final textTheme = GoogleFonts.manropeTextTheme(base.textTheme).copyWith(
      bodyMedium: GoogleFonts.manrope(fontSize: 14, color: textMain),
      titleLarge: GoogleFonts.manrope(fontSize: 22, fontWeight: FontWeight.w700),
      titleMedium: GoogleFonts.manrope(fontSize: 16, fontWeight: FontWeight.w700),
      labelLarge: GoogleFonts.manrope(fontWeight: FontWeight.w600),
    );

    final colorScheme = ColorScheme.fromSeed(
      seedColor: primary,
      primary: primary,
      secondary: primaryStrong,
      surface: surface,
      error: const Color(0xFFEF4444),
    );

    return base.copyWith(
      colorScheme: colorScheme,
      textTheme: textTheme,
      scaffoldBackgroundColor: background,
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        foregroundColor: textMain,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        margin: EdgeInsets.zero,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surfaceAlt,
        indicatorColor: const Color(0xFFDFF3EA),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => textTheme.labelSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: states.contains(WidgetState.selected) ? textMain : textMuted,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected) ? primary : textMuted,
          ),
        ),
      ),
      dividerColor: border,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: primary),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: textTheme.labelLarge,
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: surfaceAlt,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        labelStyle: textTheme.labelMedium?.copyWith(color: textMuted),
      ),
    );
  }
}
