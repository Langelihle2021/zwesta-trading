class User {
  final int id;
  final String username;
  final String email;
  final String fullName;
  final String phoneNumber;

  User({
    required this.id,
    required this.username,
    required this.email,
    required this.fullName,
    required this.phoneNumber,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? 0,
      username: json['username'] ?? '',
      email: json['email'] ?? '',
      fullName: json['fullName'] ?? json['full_name'] ?? '',
      phoneNumber: json['phoneNumber'] ?? json['phone_number'] ?? '',
    );
  }
}
