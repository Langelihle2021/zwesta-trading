import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:zwesta_trading/models/user.dart';
import 'package:zwesta_trading/services/auth_service.dart';

void main() {
  group('AuthService Tests', () {
    late AuthService authService;

    setUp(() async {
      // Setup shared preferences for testing
      SharedPreferences.setMockInitialValues({});
      authService = AuthService();
    });

    test('Initial state should be unauthenticated', () {
      expect(authService.isAuthenticated, false);
      expect(authService.currentUser, null);
      expect(authService.token, null);
    });

    test('Login with valid credentials should succeed', () async {
      final success = await authService.login('demo', 'demo123');
      
      expect(success, true);
      expect(authService.isAuthenticated, true);
      expect(authService.currentUser, isNotNull);
      expect(authService.currentUser?.username, 'demo');
      expect(authService.token, isNotNull);
    });

    test('Login with empty credentials should fail', () async {
      final success = await authService.login('', '');
      
      expect(success, false);
      expect(authService.isAuthenticated, false);
      expect(authService.errorMessage, isNotNull);
    });

    test('Register with valid data should succeed', () async {
      final success = await authService.register(
        'testuser',
        'test@example.com',
        'password123',
        'John',
        'Doe',
      );

      expect(success, true);
      expect(authService.isAuthenticated, true);
      expect(authService.currentUser, isNotNull);
      expect(authService.currentUser?.email, 'test@example.com');
      expect(authService.currentUser?.firstName, 'John');
      expect(authService.currentUser?.lastName, 'Doe');
    });

    test('Register with empty fields should fail', () async {
      final success = await authService.register(
        '',
        '',
        '',
        '',
        '',
      );

      expect(success, false);
      expect(authService.isAuthenticated, false);
      expect(authService.errorMessage, isNotNull);
    });

    test('Logout should clear user data', () async {
      // Login first
      await authService.login('demo', 'demo123');
      expect(authService.isAuthenticated, true);

      // Logout
      await authService.logout();
      
      expect(authService.isAuthenticated, false);
      expect(authService.currentUser, null);
      expect(authService.token, null);
    });

    test('Update profile should modify user data', () async {
      // Login first
      await authService.login('demo', 'demo123');
      
      final success = await authService.updateProfile(
        'Jane',
        'Smith',
        'jane@example.com',
      );

      expect(success, true);
      expect(authService.currentUser?.firstName, 'Jane');
      expect(authService.currentUser?.lastName, 'Smith');
      expect(authService.currentUser?.email, 'jane@example.com');
    });

    test('Change password should succeed', () async {
      // Login first
      await authService.login('demo', 'demo123');
      
      final success = await authService.changePassword(
        'demo123',
        'newpassword123',
      );

      expect(success, true);
      expect(authService.errorMessage, null);
    });

    test('Clear error message should remove error', () {
      authService.clearErrorMessage();
      expect(authService.errorMessage, null);
    });
  });

  group('User Model Tests', () {
    test('User model should be created correctly', () {
      final user = User(
        id: '1',
        username: 'testuser',
        email: 'test@example.com',
        firstName: 'Test',
        lastName: 'User',
        accountType: 'Premium',
      );

      expect(user.id, '1');
      expect(user.username, 'testuser');
      expect(user.email, 'test@example.com');
      expect(user.fullName, 'Test User');
      expect(user.accountType, 'Premium');
    });

    test('User.fromJson should create user from JSON', () {
      final json = {
        'id': '123',
        'username': 'john',
        'email': 'john@example.com',
        'firstName': 'John',
        'lastName': 'Doe',
        'accountType': 'Standard',
      };

      final user = User.fromJson(json);

      expect(user.id, '123');
      expect(user.username, 'john');
      expect(user.fullName, 'John Doe');
    });

    test('User.toJson should convert user to JSON', () {
      final user = User(
        id: '1',
        username: 'test',
        email: 'test@example.com',
        firstName: 'Test',
        lastName: 'User',
      );

      final json = user.toJson();

      expect(json['id'], '1');
      expect(json['username'], 'test');
      expect(json['email'], 'test@example.com');
      expect(json['firstName'], 'Test');
    });
  });
}
