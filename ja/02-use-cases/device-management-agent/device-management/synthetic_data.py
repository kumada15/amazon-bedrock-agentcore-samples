"""
デバイス管理システム - 合成データジェネレーター

このモジュールは、デバイス管理システム用のリアルな合成テストデータを生成し、
DynamoDB テーブルにデバイス、ユーザー、WiFi ネットワーク、デバイス設定、
およびユーザーアクティビティを投入します。包括的なテストとデモンストレーション
のための最小データ要件を満たすことを保証します。

ジェネレーターが作成するもの:
- 25台以上のリアルな設定を持つ IoT デバイス
- デバイスごとに25以上のデバイス設定（合計600以上の設定）
- デバイス間で25以上の WiFi ネットワーク
- 様々なロールを持つ25以上のユーザーアカウント
- 625以上のユーザーアクティビティレコード（ユーザーあたり25件）

主な機能:
    - リアルなデバイスモデル（TransPort ルーター、IX/EX シリーズ）
    - 包括的なデバイス設定（セルラー、ネットワーク、システム、セキュリティ）
    - 多様な WiFi 設定（セキュリティタイプ、チャンネル、信号強度）
    - 多様なユーザーロール（admin、operator、viewer、technician など）
    - 豊富なアクティビティ履歴（ログイン、設定変更、ファームウェア更新）
    - 履歴データ用のタイムスタンプ生成
    - 競合を防ぐための一意のメールアドレス
    - DynamoDB 互換の ISO 形式日時文字列

データ生成の詳細:

    デバイス (25以上):
    - デバイス ID: DG-100001 から DG-100025
    - モデル: TransPort WR31/WR44、IX20/IX15、EX15/EX12、WR54/WR64
    - ファームウェアバージョン: 5.x.x 形式
    - 接続状態: Connected、Disconnected、Dormant、Maintenance、Updating
    - IP アドレス: 192.168.x.x 範囲
    - MAC アドレス: 00:40:9D:xx:xx:xx 形式
    - 最終接続: 過去72時間以内

    デバイス設定 (デバイスあたり25件):
    - セルラー: APN、認証タイプ、SIM PIN、バンド選択、ローミング
    - ネットワーク: ホスト名、IP モード、DNS、ゲートウェイ、MTU、IPv6
    - システム: 連絡先、ロケーション、説明、タイムゾーン、NTP、ログレベル
    - ファイアウォール: 有効状態、デフォルトポリシー
    - WiFi: チャンネル、国、規制ドメイン
    - セキュリティ: SSH、HTTPS、パスワード複雑性

    WiFi ネットワーク (合計25以上):
    - ネットワーク ID: wifi_1、wifi_2 など
    - SSID: Device-Net-{device_id}-{number}
    - セキュリティタイプ: WPA2-PSK、WPA3-PSK、Open、WPA-PSK、WEP、Enterprise
    - チャンネル: 1、6、11（2.4GHz）、36-161（5GHz）
    - 信号強度: -90 から -30 dBm
    - 有効状態: 主に有効（80%の確率）

    ユーザー (25以上):
    - ユーザー ID: USR100001 から USR100025
    - ユーザー名: firstname.lastname{number}
    - メール: 複数ドメインにわたって一意
    - ロール: admin、operator、viewer、device_admin、support、manager など
    - 作成日: 30〜365日前
    - 最終ログイン: 1〜240時間前

    ユーザーアクティビティ (合計625以上、ユーザーあたり25件):
    - アクティビティタイプ: 以下を含む30種類:
      * 認証: login、logout、password_change
      * デバイス操作: config_change、firmware_update、reboot
      * ユーザー管理: user_added、user_removed、permission_changed
      * システム操作: backup、restore、report_generated
      * ネットワーク: VPN connected/disconnected、remote_access
      * セキュリティ: 証明書操作、security_scan
    - タイムスタンプ: 過去30日間に分散
    - IP アドレス: 様々なソース IP
    - 説明: コンテキスト固有の詳細

環境変数:
    AWS_REGION: DynamoDB 用の AWS リージョン（デフォルトは us-west-2）

投入される DynamoDB テーブル:
    - Devices: デバイスインベントリとステータス
    - DeviceSettings: デバイスごとの設定
    - WifiNetworks: WiFi ネットワーク設定
    - Users: ユーザーアカウントとプロファイル
    - UserActivities: アクティビティログと監査証跡

使用方法:
    直接実行してデータを生成:
    >>> python synthetic_data.py

    プログラムからインポートして使用:
    >>> from synthetic_data import generate_synthetic_data
    >>> generate_synthetic_data()

出力:
    合成データが正常に生成されました！
    - 25台のデバイスを作成
    - 25人のユーザーを作成
    - 25件の WiFi ネットワークを作成
    - 625件のデバイス設定を作成
    - 625件のユーザーアクティビティを作成

データ特性:
    - 全てのタイムスタンプは ISO 8601 形式
    - 数値には Decimal 型を使用（DynamoDB 互換性）
    - リアルな値の分布（純粋にランダムではない）
    - 参照整合性（アクティビティは実際のユーザー/デバイスを参照）
    - 異なるクエリパターンをテストするための多様なデータ

注意事項:
    - 最初に DynamoDB テーブルを初期化する必要があります
    - dynamodb_models.py から init_db() を自動的に呼び出します
    - DynamoDB 操作に boto3 を使用
    - 決定論的データを生成（同じ実行で類似パターンを生成）
    - 複数回実行しても安全（新しいレコードを作成）
    - エンティティタイプごとに最低25項目を保証
    - リトライロジックでメールの一意性を確保
"""
import datetime
import random
import uuid
from decimal import Decimal
import boto3

# DynamoDB 接続の設定
# 常に us-west-2 の AWS DynamoDB を使用
aws_region = 'us-west-2'

# DynamoDB リソースの初期化
dynamodb = boto3.resource('dynamodb', region_name=aws_region)

# テーブル名の定義
DEVICES_TABLE = 'Devices'
DEVICE_SETTINGS_TABLE = 'DeviceSettings'
WIFI_NETWORKS_TABLE = 'WifiNetworks'
USERS_TABLE = 'Users'
USER_ACTIVITIES_TABLE = 'UserActivities'

# datetime を ISO 形式文字列に変換するヘルパー関数
def datetime_to_iso(dt):
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt

# デバイス CRUD 操作
def create_device(device_data):
    """新しいデバイスを作成します"""
    table = dynamodb.Table(DEVICES_TABLE)
    
    # device_id が存在することを確認
    if 'device_id' not in device_data:
        device_data['device_id'] = f"DG-{uuid.uuid4().hex[:8].upper()}"
    
    # datetime オブジェクトを ISO 形式文字列に変換
    if 'last_connected' in device_data and device_data['last_connected']:
        device_data['last_connected'] = datetime_to_iso(device_data['last_connected'])
    
    table.put_item(Item=device_data)
    return device_data

# デバイス設定 CRUD 操作
def create_device_setting(device_id, setting_key, setting_value, last_updated=None):
    """デバイス設定を作成または更新します"""
    table = dynamodb.Table(DEVICE_SETTINGS_TABLE)
    
    if not last_updated:
        last_updated = datetime.datetime.utcnow()
    
    item = {
        'device_id': device_id,
        'setting_key': setting_key,
        'setting_value': setting_value,
        'last_updated': datetime_to_iso(last_updated)
    }
    
    table.put_item(Item=item)
    return item

# WiFi ネットワーク CRUD 操作
def create_wifi_network(network_data):
    """新しい WiFi ネットワークを作成します"""
    table = dynamodb.Table(WIFI_NETWORKS_TABLE)
    
    # 必須フィールドが存在することを確認
    if 'device_id' not in network_data:
        raise ValueError("device_id is required")
    
    if 'network_id' not in network_data:
        network_data['network_id'] = f"wifi_{uuid.uuid4().hex[:8]}"
    
    # datetime オブジェクトを ISO 形式文字列に変換
    if 'last_updated' in network_data and network_data['last_updated']:
        network_data['last_updated'] = datetime_to_iso(network_data['last_updated'])
    else:
        network_data['last_updated'] = datetime_to_iso(datetime.datetime.utcnow())

    # DynamoDB 用に float を Decimal に変換
    if 'signal_strength' in network_data and network_data['signal_strength'] is not None:
        network_data['signal_strength'] = Decimal(str(network_data['signal_strength']))
    
    table.put_item(Item=network_data)
    return network_data

# ユーザー CRUD 操作
def create_user(user_data):
    """新しいユーザーを作成します"""
    table = dynamodb.Table(USERS_TABLE)
    
    # user_id が存在することを確認
    if 'user_id' not in user_data:
        user_data['user_id'] = f"USR{uuid.uuid4().hex[:8].upper()}"
    
    # datetime オブジェクトを ISO 形式文字列に変換
    if 'created_at' in user_data and user_data['created_at']:
        user_data['created_at'] = datetime_to_iso(user_data['created_at'])
    else:
        user_data['created_at'] = datetime_to_iso(datetime.datetime.utcnow())

    if 'last_login' in user_data and user_data['last_login']:
        user_data['last_login'] = datetime_to_iso(user_data['last_login'])
    
    table.put_item(Item=user_data)
    return user_data

# ユーザーアクティビティ CRUD 操作
def create_user_activity(user_id, activity_type, description=None, ip_address=None, timestamp=None):
    """新しいユーザーアクティビティを作成します"""
    table = dynamodb.Table(USER_ACTIVITIES_TABLE)
    
    if not timestamp:
        timestamp = datetime.datetime.utcnow()
    
    timestamp_str = datetime_to_iso(timestamp)
    
    item = {
        'user_id': user_id,
        'timestamp': timestamp_str,
        'activity_type': activity_type,
        'description': description,
        'ip_address': ip_address
    }
    
    table.put_item(Item=item)
    return item

def generate_synthetic_data():
    """DynamoDB を使用したテスト用の合成データを生成します"""
    # データベースをインポートして初期化
    from dynamodb_models import init_db
    init_db()
    
    # デバイスを生成（25台以上）
    devices = []
    for i in range(1, 26):
        device_id = f"DG-{100000+i}"
        device_data = {
            'device_id': device_id,
            'name': f"Device Router {i}",
            'model': random.choice(["TransPort WR31", "TransPort WR44", "IX20", "EX15", "IX15", "EX12", "WR54", "WR64"]),
            'firmware_version': f"5.{random.randint(1, 9)}.{random.randint(1, 20)}",
            'connection_status': random.choice(["Connected", "Disconnected", "Dormant", "Maintenance", "Updating"]),
            'ip_address': f"192.168.{random.randint(1, 5)}.{random.randint(2, 254)}",
            'mac_address': f"00:40:9D:{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}",
            'last_connected': datetime.datetime.now() - datetime.timedelta(hours=random.randint(0, 72))
        }
        device = create_device(device_data)
        devices.append(device)
    
    # デバイス設定を生成（デバイスごとに複数）
    setting_keys = [
        "cellular.apn", "cellular.auth_type", "cellular.sim_pin", 
        "network.hostname", "network.ip_mode", "network.dns_primary",
        "system.contact", "system.location", "system.description",
        "firewall.enabled", "firewall.default_policy",
        "wifi.channel", "wifi.country", "wifi.regulatory_domain",
        "system.timezone", "system.ntp_server", "system.log_level",
        "network.ipv6_enabled", "network.mtu", "network.gateway",
        "security.ssh_enabled", "security.https_enabled", "security.password_complexity",
        "cellular.band_selection", "cellular.roaming_allowed"
    ]
    
    device_settings_count = 0
    for device in devices:
        # 各デバイスに各キーの設定が少なくとも1つ存在することを確認
        for key in setting_keys:
            if "cellular.apn" in key:
                value = random.choice(["internet", "broadband", "iot.secure", "m2m.provider.com", "wireless.data"])
            elif "auth_type" in key:
                value = random.choice(["none", "pap", "chap", "auto"])
            elif "sim_pin" in key:
                value = str(random.randint(1000, 9999))
            elif "hostname" in key:
                value = f"device-router-{device['device_id'].lower()}"
            elif "ip_mode" in key:
                value = random.choice(["dhcp", "static", "auto"])
            elif "dns" in key:
                value = random.choice(["8.8.8.8", "8.8.4.4", "1.1.1.1", "9.9.9.9", f"192.168.{random.randint(1,5)}.1"])
            elif "contact" in key:
                value = f"admin-{random.randint(1, 10)}@example.com"
            elif "location" in key:
                value = random.choice(["Server Room", "Office", "Remote Site", "Branch Office", "Warehouse", 
                                      "Data Center", "Manufacturing Floor", "Retail Store", "Distribution Center", "Field Site"])
            elif "description" in key:
                value = f"Device Router for {random.choice(['Primary', 'Backup', 'IoT', 'Monitoring', 'Security', 'Guest', 'VPN', 'Emergency'])} connectivity"
            elif "firewall.enabled" in key:
                value = random.choice(["true", "false"])
            elif "default_policy" in key:
                value = random.choice(["accept", "drop", "reject"])
            elif "wifi.channel" in key:
                value = str(random.choice([1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]))
            elif "wifi.country" in key:
                value = random.choice(["US", "CA", "GB", "DE", "FR", "JP", "AU", "NZ", "SG", "IN"])
            elif "regulatory_domain" in key:
                value = random.choice(["FCC", "ETSI", "TELEC", "KCC", "SRRC"])
            elif "timezone" in key:
                value = random.choice(["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney", "Pacific/Auckland"])
            elif "ntp_server" in key:
                value = random.choice(["pool.ntp.org", "time.google.com", "time.windows.com", "time.apple.com", "ntp.ubuntu.com"])
            elif "log_level" in key:
                value = random.choice(["debug", "info", "warning", "error", "critical"])
            elif "ipv6_enabled" in key:
                value = random.choice(["true", "false"])
            elif "mtu" in key:
                value = str(random.choice([1500, 1492, 1480, 1450, 1400]))
            elif "gateway" in key:
                value = f"192.168.{random.randint(1,5)}.1"
            elif "ssh_enabled" in key:
                value = random.choice(["true", "false"])
            elif "https_enabled" in key:
                value = random.choice(["true", "false"])
            elif "password_complexity" in key:
                value = random.choice(["low", "medium", "high", "extreme"])
            elif "band_selection" in key:
                value = random.choice(["auto", "4g_only", "5g_only", "4g_preferred", "5g_preferred"])
            elif "roaming_allowed" in key:
                value = random.choice(["true", "false"])
            else:
                value = f"value-{random.randint(1, 100)}"
                
            last_updated = datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 30))
            create_device_setting(device['device_id'], key, value, last_updated)
            device_settings_count += 1
    
    # WiFi ネットワークを生成（合計25件以上）
    wifi_count = 0
    for device in devices:
        # 合計25件以上の WiFi ネットワークがあることを確認
        networks_per_device = max(1, 25 // len(devices))
        if wifi_count < 25 and device['device_id'] == devices[-1]['device_id']:
            # 25件以上を確保するため、残りのネットワークを最後のデバイスに追加
            networks_per_device = max(networks_per_device, 25 - wifi_count)
            
        for i in range(1, networks_per_device + 1):
            network_data = {
                'device_id': device['device_id'],
                'network_id': f"wifi_{i}",
                'ssid': f"Device-Net-{device['device_id']}-{i}",
                'security_type': random.choice(["wpa2-psk", "wpa3-psk", "open", "wpa-psk", "wep", "enterprise"]),
                'enabled': random.choice([True, True, False]),  # 有効になる確率が高い
                'channel': random.choice([1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161]),
                'signal_strength': random.uniform(-90.0, -30.0),
                'last_updated': datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 30))
            }
            create_wifi_network(network_data)
            wifi_count += 1
    
    # ユーザーを生成（25人以上）
    users = []
    roles = ["admin", "operator", "viewer", "device_admin", "support", "manager", "auditor", "guest", "technician", "developer"]
    domains = ["example.com", "company.net", "device-test.org", "enterprise.co", "tech-corp.io"]
    
    first_names = ["John", "Jane", "Robert", "Lisa", "Michael", "Sarah", "David", "Emma", "Chris", "Olivia", 
                  "William", "Sophia", "James", "Ava", "Benjamin", "Mia", "Daniel", "Charlotte", "Matthew", "Amelia",
                  "Joseph", "Harper", "Andrew", "Evelyn", "Joshua", "Abigail", "Nicholas", "Emily", "Ryan", "Elizabeth"]
    
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Wilson", "Taylor",
                 "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson", "Moore", "Young", "Allen",
                 "King", "Wright", "Scott", "Green", "Baker", "Adams", "Nelson", "Hill", "Ramirez", "Campbell"]
    
    # 使用済みメールアドレスを追跡するセットを作成
    used_emails = set()
    
    for i in range(1, 26):
        # 一意のメールアドレスが得られるまで生成を続ける
        while True:
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            domain = random.choice(domains)
            email = f"{first_name.lower()}.{last_name.lower()}{i}@{domain}"
            
            if email not in used_emails:
                used_emails.add(email)
                break
        
        user_data = {
            'user_id': f"USR{100000+i}",
            'username': f"{first_name.lower()}.{last_name.lower()}{i}",
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'role': random.choice(roles),
            'created_at': datetime.datetime.now() - datetime.timedelta(days=random.randint(30, 365)),
            'last_login': datetime.datetime.now() - datetime.timedelta(hours=random.randint(1, 240))
        }
        user = create_user(user_data)
        users.append(user)
    
    # ユーザーアクティビティを生成（ユーザーあたり25件以上）
    activity_types = [
        "login", "logout", "device_config_change", "firmware_update", 
        "user_added", "user_removed", "report_generated", "alert_acknowledged",
        "device_reboot", "password_change", "vpn_connected", "vpn_disconnected",
        "file_upload", "file_download", "settings_export", "settings_import",
        "group_created", "group_modified", "permission_changed", "api_key_created",
        "api_key_revoked", "schedule_created", "schedule_modified", "backup_created",
        "restore_performed", "certificate_installed", "certificate_expired", "security_scan",
        "remote_access_enabled", "remote_access_disabled"
    ]
    
    user_activities_count = 0
    for user in users:
        # ユーザーあたり少なくとも25件のアクティビティを生成
        for _ in range(25):
            activity_type = random.choice(activity_types)
            
            if activity_type == "login":
                description = f"User logged in from {random.choice(['web interface', 'mobile app', 'API', 'CLI', 'desktop application'])}"
            elif activity_type == "logout":
                description = "User logged out"
            elif activity_type == "device_config_change":
                device = random.choice(devices)
                setting = random.choice(setting_keys)
                description = f"Changed {setting} on device {device['name']}"
            elif activity_type == "firmware_update":
                device = random.choice(devices)
                old_version = f"5.{random.randint(1, 5)}.{random.randint(1, 10)}"
                new_version = f"5.{random.randint(6, 9)}.{random.randint(1, 20)}"
                description = f"Updated firmware on {device['name']} from {old_version} to {new_version}"
            elif activity_type == "user_added":
                description = f"Added new user {random.choice(first_names).lower()}.{random.choice(last_names).lower()}"
            elif activity_type == "user_removed":
                description = f"Removed user {random.choice(first_names).lower()}.{random.choice(last_names).lower()}"
            elif activity_type == "report_generated":
                report_type = random.choice(["usage", "security", "connectivity", "performance", "compliance", "audit", "inventory"])
                description = f"Generated {report_type} report"
            elif activity_type == "alert_acknowledged":
                alert_id = f"ALT-{random.randint(10000, 99999)}"
                description = f"Acknowledged alert {alert_id}"
            elif activity_type == "device_reboot":
                device = random.choice(devices)
                description = f"Initiated reboot of device {device['name']}"
            elif activity_type == "password_change":
                description = "Changed account password"
            elif activity_type == "vpn_connected":
                description = f"Connected to VPN from IP {random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
            elif activity_type == "vpn_disconnected":
                description = "Disconnected from VPN"
            elif activity_type == "file_upload":
                file_type = random.choice(["configuration", "firmware", "certificate", "log", "backup"])
                description = f"Uploaded {file_type} file"
            elif activity_type == "file_download":
                file_type = random.choice(["configuration", "report", "log", "backup", "template"])
                description = f"Downloaded {file_type} file"
            elif activity_type == "settings_export":
                device = random.choice(devices)
                description = f"Exported settings from device {device['name']}"
            elif activity_type == "settings_import":
                device = random.choice(devices)
                description = f"Imported settings to device {device['name']}"
            elif activity_type == "group_created":
                description = "Created device group '{}'".format(random.choice(['Production', 'Testing', 'Development', 'Backup', 'Remote', 'Office', 'Warehouse']))
            elif activity_type == "group_modified":
                description = f"Modified device group '{random.choice(['Production', 'Testing', 'Development', 'Backup', 'Remote', 'Office', 'Warehouse'])}'"
            elif activity_type == "permission_changed":
                target_user = random.choice(users)
                description = f"Changed permissions for user {target_user['username']}"
            elif activity_type == "api_key_created":
                description = "Created new API key"
            elif activity_type == "api_key_revoked":
                description = "Revoked API key"
            elif activity_type == "schedule_created":
                task = random.choice(["backup", "reboot", "firmware update", "report generation", "maintenance"])
                description = f"Created schedule for {task}"
            elif activity_type == "schedule_modified":
                task = random.choice(["backup", "reboot", "firmware update", "report generation", "maintenance"])
                description = f"Modified schedule for {task}"
            elif activity_type == "backup_created":
                device = random.choice(devices)
                description = f"Created backup of device {device['name']}"
            elif activity_type == "restore_performed":
                device = random.choice(devices)
                description = f"Restored configuration to device {device['name']}"
            elif activity_type == "certificate_installed":
                device = random.choice(devices)
                cert_type = random.choice(["SSL", "SSH", "CA", "client"])
                description = f"Installed {cert_type} certificate on device {device['name']}"
            elif activity_type == "certificate_expired":
                device = random.choice(devices)
                cert_type = random.choice(["SSL", "SSH", "CA", "client"])
                description = f"{cert_type} certificate expired on device {device['name']}"
            elif activity_type == "security_scan":
                device = random.choice(devices)
                description = f"Performed security scan on device {device['name']}"
            elif activity_type == "remote_access_enabled":
                device = random.choice(devices)
                description = f"Enabled remote access for device {device['name']}"
            elif activity_type == "remote_access_disabled":
                device = random.choice(devices)
                description = f"Disabled remote access for device {device['name']}"
            else:
                description = f"Performed {activity_type}"
                
            # 過去30日以内のタイムスタンプを生成
            timestamp = datetime.datetime.now() - datetime.timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            ip_address = f"{random.randint(10, 203)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            
            create_user_activity(user['user_id'], activity_type, description, ip_address, timestamp)
            user_activities_count += 1
    
    print("合成データが正常に生成されました！")
    print(f"- {len(devices)} 台のデバイスを作成")
    print(f"- {len(users)} 人のユーザーを作成")
    print(f"- {wifi_count} 件の WiFi ネットワークを作成")
    print(f"- {device_settings_count} 件のデバイス設定を作成")
    print(f"- {user_activities_count} 件のユーザーアクティビティを作成")

if __name__ == "__main__":
    generate_synthetic_data()
