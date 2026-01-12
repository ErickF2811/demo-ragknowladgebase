import 'package:flutter/material.dart';

import '../app_scope.dart';
import 'calendar_screen.dart';
import 'clients_screen.dart';
import 'files_screen.dart';
import 'settings_screen.dart';
import 'workspace_picker_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final scope = AppScope.of(context);
    if (scope.workspace.schema.trim().isEmpty) {
      return const WorkspacePickerScreen();
    }

    final screens = <Widget>[
      CalendarScreen(
        key: const PageStorageKey('calendar'),
        active: _selectedIndex == 0,
      ),
      ClientsScreen(
        key: const PageStorageKey('clients'),
        active: _selectedIndex == 1,
      ),
      FilesScreen(
        key: const PageStorageKey('files'),
        active: _selectedIndex == 2,
      ),
      SettingsScreen(
        key: const PageStorageKey('settings'),
        active: _selectedIndex == 3,
      ),
    ];
    return Scaffold(
      body: SafeArea(
        child: IndexedStack(
          index: _selectedIndex,
          children: screens,
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onItemTapped,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.event), label: 'Agenda'),
          NavigationDestination(icon: Icon(Icons.people_alt), label: 'Clientes'),
          NavigationDestination(icon: Icon(Icons.folder), label: 'Archivos'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Ajustes'),
        ],
      ),
    );
  }
}
