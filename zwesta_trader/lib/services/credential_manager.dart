import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/user_models.dart';

class CredentialManager extends ChangeNotifier {
  User? _currentUser;
  final List<User> _users = [];
  late SharedPreferences _prefs;

  User? get currentUser => _currentUser;
  List<User> get users => _users;

  Future<void> initialize() async {
    _prefs = await SharedPreferences.getInstance();
    await _loadUsers();
  }

  Future<void> _loadUsers() async {
    final userIds = _prefs.getStringList('user_ids') ?? [];
    for (final id in userIds) {
      final userData = _prefs.getString('user_$id');
      if (userData != null) {
        _users.add(User.fromJson(userData));
      }
    }
    notifyListeners();
  }

  Future<bool> registerUser(String firstName, String lastName, String email,
      String username, String password,
      {required String brokerId,
      required String brokerName,
      required String accountNumber,
      required String apiKey,
      required String accountType}) async {
    const uuid = Uuid();
    final userId = uuid.v4();
    final accountId = uuid.v4();

    final user = User(
      userId: userId,
      username: username,
      email: email,
      tradingAccounts: [
        TradingAccount(
          accountId: accountId,
          brokerId: brokerId,
          brokerName: brokerName,
          accountNumber: accountNumber,
          apiKey: apiKey,
          accountType: accountType,
          maxDailyLoss: 100,
          maxSessionLoss: 50,
          maxConsecutiveLosses: 3,
          isDefault: true,
          isActive: true,
        ),
      ],
      currentAccount: accountId,
      createdAt: DateTime.now(),
      lastLogin: DateTime.now(),
    );

    _users.add(user);
    _currentUser = user;

    // Save to SharedPreferences
    final userIds = _prefs.getStringList('user_ids') ?? [];
    userIds.add(userId);
    await _prefs.setStringList('user_ids', userIds);
    await _prefs.setString('user_$userId', user.toJson());
    await _prefs.setString('current_user_id', userId);

    notifyListeners();
    return true;
  }

  Future<bool> login(String username, String password) async {
    try {
      final user =
          _users.firstWhere((u) => u.username == username);
      _currentUser = user;
      await _prefs.setString('current_user_id', user.userId);
      notifyListeners();
      return true;
    } catch (e) {
      return false;
    }
  }

  Future<void> logout() async {
    _currentUser = null;
    await _prefs.remove('current_user_id');
    notifyListeners();
  }

  Future<bool> addTradingAccount(
      String brokerId,
      String brokerName,
      String accountNumber,
      String apiKey,
      String accountType) async {
    if (_currentUser == null) return false;

    const uuid = Uuid();
    final accountId = uuid.v4();

    final newAccount = TradingAccount(
      accountId: accountId,
      brokerId: brokerId,
      brokerName: brokerName,
      accountNumber: accountNumber,
      apiKey: apiKey,
      accountType: accountType,
      maxDailyLoss: 100,
      maxSessionLoss: 50,
      maxConsecutiveLosses: 3,
      isDefault: false,
      isActive: false,
    );

    _currentUser!.tradingAccounts.add(newAccount);
    await _prefs.setString('user_${_currentUser!.userId}', _currentUser!.toJson());
    notifyListeners();
    return true;
  }

  Future<bool> switchAccount(String accountId) async {
    if (_currentUser == null) return false;

    try {
      final account = _currentUser!.tradingAccounts
          .firstWhere((a) => a.accountId == accountId);
      _currentUser!.currentAccount = accountId;
      await _prefs.setString('user_${_currentUser!.userId}', _currentUser!.toJson());
      notifyListeners();
      return true;
    } catch (e) {
      return false;
    }
  }
}
