DateTime? _parseDate(dynamic value) {
  if (value == null) {
    return null;
  }
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value);
  }
  return null;
}

class Appointment {
  final int id;
  final String title;
  final String? description;
  final DateTime? startTime;
  final DateTime? endTime;
  final String? status;
  final String? timezone;
  final int? clientId;

  Appointment({
    required this.id,
    required this.title,
    this.description,
    this.startTime,
    this.endTime,
    this.status,
    this.timezone,
    this.clientId,
  });

  factory Appointment.fromJson(Map<String, dynamic> json) {
    return Appointment(
      id: json['id'] as int,
      title: (json['title'] as String?) ?? '',
      description: json['description'] as String?,
      startTime: _parseDate(json['start_time']),
      endTime: _parseDate(json['end_time']),
      status: json['status'] as String?,
      timezone: json['timezone'] as String?,
      clientId: json['client_id'] as int?,
    );
  }
}

class Client {
  final int id;
  final String fullName;
  final String idType;
  final String idNumber;
  final String? phone;
  final String? email;
  final String? address;
  final bool blacklisted;
  final String? notes;

  Client({
    required this.id,
    required this.fullName,
    required this.idType,
    required this.idNumber,
    this.phone,
    this.email,
    this.address,
    required this.blacklisted,
    this.notes,
  });

  factory Client.fromJson(Map<String, dynamic> json) {
    return Client(
      id: json['id'] as int,
      fullName: (json['full_name'] as String?) ?? '',
      idType: (json['id_type'] as String?) ?? '',
      idNumber: (json['id_number'] as String?) ?? '',
      phone: json['phone'] as String?,
      email: json['email'] as String?,
      address: json['address'] as String?,
      blacklisted: (json['blacklisted'] as bool?) ?? false,
      notes: json['notes'] as String?,
    );
  }
}

class FileItem {
  final int id;
  final String filename;
  final String? folder;
  final String? status;
  final String? blobUrl;
  final List<String> tags;
  final DateTime? createdAt;

  FileItem({
    required this.id,
    required this.filename,
    this.folder,
    this.status,
    this.blobUrl,
    required this.tags,
    this.createdAt,
  });

  factory FileItem.fromJson(Map<String, dynamic> json) {
    final tagsRaw = json['tags'];
    final tags = <String>[];
    if (tagsRaw is List) {
      for (final item in tagsRaw) {
        if (item is String) {
          tags.add(item);
        }
      }
    }
    return FileItem(
      id: json['id'] as int,
      filename: (json['filename'] as String?) ?? '',
      folder: json['folder'] as String?,
      status: json['status'] as String?,
      blobUrl: json['blob_url'] as String?,
      tags: tags,
      createdAt: _parseDate(json['created_at']),
    );
  }
}

class Workspace {
  final String id;
  final String name;
  final String schemaName;
  final String? description;
  final String? themeColor;
  final String? iconUrl;
  final String? ownerName;
  final int? filesCount;
  final int? appointmentsCount;

  Workspace({
    required this.id,
    required this.name,
    required this.schemaName,
    this.description,
    this.themeColor,
    this.iconUrl,
    this.ownerName,
    this.filesCount,
    this.appointmentsCount,
  });

  factory Workspace.fromJson(Map<String, dynamic> json) {
    return Workspace(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] as String?) ?? '',
      schemaName: (json['schema_name'] as String?) ?? (json['slug'] as String?) ?? '',
      description: json['description'] as String?,
      themeColor: json['theme_color'] as String?,
      iconUrl: json['icon_url'] as String?,
      ownerName: json['owner_name'] as String?,
      filesCount: json['files_count'] as int?,
      appointmentsCount: json['appointments_count'] as int?,
    );
  }
}
