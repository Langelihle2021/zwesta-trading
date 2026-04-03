import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  static final FlutterLocalNotificationsPlugin _notificationsPlugin = FlutterLocalNotificationsPlugin();

  static Future<void> initialize(BuildContext context) async {
    const initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const initializationSettings = InitializationSettings(
      android: initializationSettingsAndroid,
    );
    await _notificationsPlugin.initialize(initializationSettings);
  }

  static Future<void> showNotification({
    required String title,
    required String body,
    int id = 0,
  }) async {
    const androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'default_channel',
      'General',
      channelDescription: 'General notifications',
      importance: Importance.max,
      priority: Priority.high,
      showWhen: true,
    );
    const platformChannelSpecifics =
        NotificationDetails(android: androidPlatformChannelSpecifics);
    await _notificationsPlugin.show(
      id,
      title,
      body,
      platformChannelSpecifics,
    );
  }
}
