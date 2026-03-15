import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static ThemeData lightTheme = ThemeData(
    brightness: Brightness.light,
    primaryColor: const Color(0xFF1E88E5),
    colorScheme: ColorScheme.light(
      primary: const Color(0xFF1E88E5),
      secondary: const Color(0xFFFF6B6B),
      background: Colors.white,
      surface: Colors.white,
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onBackground: Colors.black,
      onSurface: Colors.black,
    ),
    scaffoldBackgroundColor: Colors.white,
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      iconTheme: IconThemeData(color: Color(0xFF1E88E5)),
      titleTextStyle: TextStyle(
        color: Color(0xFF1E88E5),
        fontWeight: FontWeight.bold,
        fontSize: 20,
      ),
    ),
    textTheme: GoogleFonts.poppinsTextTheme().copyWith(
      bodyLarge: GoogleFonts.poppins(fontSize: 16, color: Colors.black),
      bodyMedium: GoogleFonts.poppins(fontSize: 14, color: Colors.black87),
      titleLarge: GoogleFonts.poppins(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF1E88E5)),
      titleMedium: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1E88E5)),
      labelLarge: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF1E88E5)),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    ),
    buttonTheme: const ButtonThemeData(
      buttonColor: Color(0xFF1E88E5),
      textTheme: ButtonTextTheme.primary,
    ),
  );

  static ThemeData darkTheme = ThemeData(
    brightness: Brightness.dark,
    primaryColor: const Color(0xFF1E88E5),
    colorScheme: ColorScheme.dark(
      primary: const Color(0xFF1E88E5),
      secondary: const Color(0xFFFF6B6B),
      background: Color(0xFF0A0E21),
      surface: Color(0xFF1F1F1F),
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onBackground: Colors.white,
      onSurface: Colors.white,
    ),
    scaffoldBackgroundColor: const Color(0xFF0A0E21),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      iconTheme: IconThemeData(color: Colors.white),
      titleTextStyle: TextStyle(
        color: Colors.white,
        fontWeight: FontWeight.bold,
        fontSize: 20,
      ),
    ),
    textTheme: GoogleFonts.poppinsTextTheme().copyWith(
      bodyLarge: GoogleFonts.poppins(fontSize: 16, color: Colors.white),
      bodyMedium: GoogleFonts.poppins(fontSize: 14, color: Colors.white70),
      titleLarge: GoogleFonts.poppins(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
      titleMedium: GoogleFonts.poppins(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
      labelLarge: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.white),
    ),
    cardTheme: CardThemeData(
      color: const Color(0xFF1F1F1F),
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      filled: true,
      fillColor: const Color(0xFF1F1F1F),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    ),
    buttonTheme: const ButtonThemeData(
      buttonColor: Color(0xFF1E88E5),
      textTheme: ButtonTextTheme.primary,
    ),
  );
}
