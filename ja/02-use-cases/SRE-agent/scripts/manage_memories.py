#!/usr/bin/env python3
"""
SRE Agent メモリシステムのメモリを管理するヘルパースクリプト。

Usage:
    uv run python scripts/manage_memories.py [ACTION] [OPTIONS]

Actions:
    list      メモリを一覧表示（デフォルトアクション）
    update    設定ファイルからメモリを更新（重複削除あり）
    delete    メモリを削除

Examples:
    uv run python scripts/manage_memories.py                           # すべてのメモリを一覧表示
    uv run python scripts/manage_memories.py list --memory-type investigations  # investigations のみを一覧表示
    uv run python scripts/manage_memories.py update                    # user_config.yaml からユーザー設定を読み込み（重複削除）
    uv run python scripts/manage_memories.py update --config-file custom.yaml  # カスタムファイルから読み込み
    uv run python scripts/manage_memories.py update --no-duplicate-check       # 重複削除チェックをスキップ
    uv run python scripts/manage_memories.py delete --memory-id mem-123        # 特定のメモリリソースを削除
    uv run python scripts/manage_memories.py delete --memory-record-id mem-abc # 特定のメモリレコードを削除
    uv run python scripts/manage_memories.py delete --all                      # すべてのメモリリソースを削除
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

# Add the project root to path so we can import sre_agent
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bedrock_agentcore.memory import MemoryClient

from sre_agent.memory.client import SREMemoryClient
from sre_agent.memory.config import _load_memory_config
from sre_agent.memory.strategies import UserPreference, _save_user_preference

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _read_memory_id() -> str:
    """.memory_id ファイルからメモリ ID を読み取ります。"""
    memory_id_file = Path(__file__).parent.parent / ".memory_id"

    if memory_id_file.exists():
        memory_id = memory_id_file.read_text().strip()
        logger.info(f"メモリ ID を見つけました: {memory_id}（{memory_id_file} 内）")
        return memory_id

    raise FileNotFoundError("Could not find .memory_id file in project root")


def _extract_actor_from_namespace(namespace: str, memory_type: str) -> str:
    """メモリ namespace からアクター ID を抽出します。"""
    if memory_type == "preferences":
        # Preferences namespace format: /sre/users/{user_id}/preferences
        prefix = "/sre/users/"
        suffix = "/preferences"
        if namespace.startswith(prefix) and namespace.endswith(suffix):
            # Extract user_id from between prefix and suffix
            user_id = namespace[len(prefix) : -len(suffix)]
            return user_id
    else:
        # Other namespace format: /sre/{memory_type}/{actor_id}
        prefix = f"/sre/{memory_type}/"
        if namespace.startswith(prefix):
            return namespace[len(prefix) :]
    return "unknown"


def _group_memories_by_actor(memories: list, memory_type: str) -> dict:
    """namespace から抽出したアクター ID でメモリをグループ化します。"""
    actor_groups = {}

    for memory in memories:
        # Each memory can have multiple namespaces, use the first one
        if memory.get("namespaces") and len(memory["namespaces"]) > 0:
            namespace = memory["namespaces"][0]
            actor_id = _extract_actor_from_namespace(namespace, memory_type)

            if actor_id not in actor_groups:
                actor_groups[actor_id] = []
            actor_groups[actor_id].append(memory)

    return actor_groups


def _list_memories_for_type(
    client: SREMemoryClient, memory_type: str, actor_id: Optional[str] = None
) -> None:
    """特定のタイプのすべてのメモリを一覧表示します。"""
    print(f"\n=== {memory_type.upper()} メモリ ===")

    try:
        if actor_id and actor_id != "all":
            # List memories for specific actor
            memories = client.retrieve_memories(
                memory_type=memory_type,
                actor_id=actor_id,
                query="*",  # Wildcard query to get all memories
                max_results=100,
            )
            print(
                f"actor_id: {actor_id} の {memory_type} メモリを {len(memories)} 件発見しました"
            )

            for i, memory in enumerate(memories, 1):
                print(f"\n--- メモリ {i} ---")
                print(json.dumps(memory, indent=2, default=str))

        else:
            # List memories across ALL actors using broader namespace
            print(f"すべてのアクターから {memory_type} メモリを取得中...")

            # Use different namespace patterns for different memory types
            if memory_type == "preferences":
                namespace = "/sre/users"  # For user preferences: /sre/users/{user_id}/preferences
            else:
                namespace = f"/sre/{memory_type}"  # For infrastructure/investigations: /sre/{type}/{actor_id}

            memories = client.client.retrieve_memories(
                memory_id=client.memory_id,
                namespace=namespace,
                query="*",
                actor_id=None,  # No actor restriction
                top_k=100,
            )
            print(f"すべてのアクターから {memory_type} メモリを {len(memories)} 件発見しました")

            # Group memories by actor
            actor_groups = _group_memories_by_actor(memories, memory_type)

            # Display grouped by actor
            for actor, actor_memories in sorted(actor_groups.items()):
                print(f"\n--- アクター: {actor} ({len(actor_memories)} 件のメモリ) ---")

                for i, memory in enumerate(actor_memories, 1):
                    print(f"\n  メモリ {i}:")
                    print(json.dumps(memory, indent=4, default=str))

    except Exception as e:
        logger.error(f"{memory_type} メモリの取得に失敗しました: {e}")
        print(f"{memory_type} メモリの取得エラー: {e}")


def _list_all_memories() -> list:
    """すべてのメモリリソースを一覧表示します。"""
    try:
        memory_client = MemoryClient(region_name="us-east-1")
        memories = memory_client.list_memories(max_results=100)
        return memories
    except Exception as e:
        logger.error(f"メモリリソースの一覧取得に失敗しました: {e}")
        return []


def _delete_memory(memory_id: str) -> bool:
    """特定のメモリリソースを削除します。"""
    try:
        memory_client = MemoryClient(region_name="us-east-1")
        logger.info(f"メモリを削除中: {memory_id}")
        print(f"メモリを削除中: {memory_id}...")

        result = memory_client.delete_memory_and_wait(
            memory_id=memory_id, max_wait=300, poll_interval=10
        )

        logger.info(f"メモリを正常に削除しました: {memory_id}")
        print(f"メモリの削除に成功しました: {memory_id}")
        return True

    except Exception as e:
        logger.error(f"メモリ {memory_id} の削除に失敗しました: {e}")
        print(f"メモリ {memory_id} の削除エラー: {e}")
        return False


def _delete_memory_record(memory_record_id: str) -> bool:
    """ID で特定のメモリレコードを削除します。"""
    try:
        # Read the memory resource ID from .memory_id file
        memory_id = _read_memory_id()

        # Use the SREMemoryClient for proper configuration
        client = SREMemoryClient(memory_name="sre_agent_memory")

        logger.info(
            f"Deleting memory record: {memory_record_id} from memory: {memory_id}"
        )
        print(f"メモリレコードを削除中: {memory_record_id}...")

        # Use the underlying data plane client to delete the specific memory record
        result = client.client.gmdp_client.delete_memory_record(
            memoryId=memory_id, memoryRecordId=memory_record_id
        )

        logger.info(f"メモリレコードを正常に削除しました: {memory_record_id}")
        print(f"メモリレコードの削除に成功しました: {memory_record_id}")
        return True

    except Exception as e:
        logger.error(f"メモリレコード {memory_record_id} の削除に失敗しました: {e}")
        print(f"メモリレコード {memory_record_id} の削除エラー: {e}")
        return False


def _delete_all_memories() -> int:
    """すべてのメモリリソースを削除します。"""
    memories = _list_all_memories()
    if not memories:
        print("削除するメモリが見つかりません。")
        return 0

    print(f"{len(memories)} 件のメモリリソースを発見しました:")
    for memory in memories:
        memory_id = memory.get("id", "unknown")
        memory_name = memory.get("name", "unnamed")
        print(f"  - {memory_id} ({memory_name})")

    # Confirm deletion
    response = input(
        f"\n{len(memories)} 件のメモリリソースをすべて削除してよろしいですか？ (yes/no): "
    )
    if response.lower() not in ["yes", "y"]:
        print("削除をキャンセルしました。")
        return 0

    deleted_count = 0
    for memory in memories:
        memory_id = memory.get("id")
        if memory_id and _delete_memory(memory_id):
            deleted_count += 1

    print(f"\n{len(memories)} 件中 {deleted_count} 件のメモリリソースを削除しました。")
    return deleted_count


def _check_and_delete_existing_preference(
    client: SREMemoryClient, user_id: str, preference_type: str
) -> tuple[int, list]:
    """同じタイプの既存の設定イベントを確認し、重複を防ぐために削除します。"""
    try:
        # List events for this user to find duplicate preferences
        # We use list_events because it shows individual preference events, not aggregated memories
        events = client.client.list_events(
            memory_id=client.memory_id,
            actor_id=user_id,
            session_id="preferences-default",
            max_results=100,  # Get more events to ensure we find all duplicates
            include_payload=True,
        )

        deleted_count = 0
        logger.debug(f"Found {len(events)} events for user {user_id}")

        # Track which events to delete (we'll batch delete them)
        events_to_delete = []

        for event in events:
            try:
                # Get the event payload (it's a list of message objects)
                payload = event.get("payload", [])

                for message_obj in payload:
                    # Extract the conversational content
                    conversational = message_obj.get("conversational", {})
                    role = conversational.get("role", "")
                    content_obj = conversational.get("content", {})
                    content = content_obj.get("text", "")

                    # We're looking for ASSISTANT messages with preference data
                    if role == "ASSISTANT" and content:
                        import json

                        try:
                            # Parse the content to check preference type
                            pref_data = json.loads(content)

                            # Check if this is a preference with the matching type
                            if pref_data.get("preference_type") == preference_type:
                                event_id = event.get("eventId")
                                event_time = event.get("eventTimestamp")
                                logger.info(
                                    f"Found existing {preference_type} preference event: {event_id} from {event_time}"
                                )
                                events_to_delete.append(event_id)

                        except json.JSONDecodeError:
                            # Not JSON or not a preference - skip
                            continue

            except Exception as e:
                logger.warning(f"重複イベントのチェック中にエラーが発生しました: {e}")
                continue

        # Report on duplicate events found
        if events_to_delete:
            logger.info(
                f"Found {len(events_to_delete)} existing {preference_type} preference events for user {user_id}"
            )
            # Note: The Amazon Bedrock Agent Memory service doesn't support deleting individual events
            # Events are immutable and designed to accumulate over time
            # The memory strategies will aggregate all events, giving more weight to recent ones
            logger.info(
                "Note: Existing preference events cannot be deleted (events are immutable)"
            )
            logger.info(
                "New preference will be added and the memory strategy will aggregate all events"
            )
            deleted_count = 0  # We can't actually delete events

        if deleted_count > 0:
            logger.info(
                f"Deleted {deleted_count} existing {preference_type} preferences for user {user_id}"
            )

        return deleted_count, events_to_delete

    except Exception as e:
        logger.warning(
            f"Failed to check for existing preferences for user {user_id}, type {preference_type}: {e}"
        )
        return 0, []


def _load_user_preferences_from_yaml(yaml_file: Path) -> dict:
    """YAML 設定ファイルからユーザー設定を読み込みます。"""
    try:
        with open(yaml_file, "r") as f:
            config = yaml.safe_load(f)

        if not config or "users" not in config:
            raise ValueError("Invalid YAML format: missing 'users' section")

        logger.info(f"{yaml_file} からユーザー設定を読み込みました")
        return config["users"]

    except Exception as e:
        logger.error(f"{yaml_file} からユーザー設定の読み込みに失敗しました: {e}")
        raise


def _handle_update_action(args) -> None:
    """YAML からユーザー設定を読み込む update アクションを処理します。"""
    try:
        # Default YAML file path (look in scripts directory first, then project root)
        yaml_file = Path(__file__).parent / "user_config.yaml"
        if not yaml_file.exists():
            yaml_file = Path(__file__).parent.parent / "user_config.yaml"

        # Use custom path if provided
        if hasattr(args, "config_file") and args.config_file:
            yaml_file = Path(args.config_file)

        if not yaml_file.exists():
            print(f"エラー: 設定ファイルが見つかりません: {yaml_file}")
            sys.exit(1)

        print(f"ユーザー設定を読み込み中: {yaml_file}")

        # Load user preferences from YAML
        users_config = _load_user_preferences_from_yaml(yaml_file)

        # Create memory client
        client = SREMemoryClient(memory_name="sre_agent_memory")

        total_added = 0
        total_deleted = 0
        total_users = len(users_config)

        if args.no_duplicate_check:
            print(
                f"{total_users} ユーザーの設定を処理中（重複チェック無効）..."
            )
        else:
            print(
                f"{total_users} ユーザーの設定を処理中（重複を削除）..."
            )

        # Process each user
        for user_id, user_config in users_config.items():
            if "preferences" not in user_config:
                print(f"警告: ユーザー {user_id} の設定が見つかりません")
                continue

            user_preferences = user_config["preferences"]
            print(
                f"\n--- ユーザー処理中: {user_id} ({len(user_preferences)} 件の設定) ---"
            )

            # Process each preference for this user
            for pref_data in user_preferences:
                try:
                    preference_type = pref_data["preference_type"]

                    # Check for and delete existing preferences of the same type (unless disabled)
                    deleted_count = 0
                    events_to_delete = []
                    if not args.no_duplicate_check:
                        deleted_count, events_to_delete = (
                            _check_and_delete_existing_preference(
                                client, user_id, preference_type
                            )
                        )

                        if deleted_count > 0:
                            # This should not happen anymore since we can't delete events
                            print(
                                f"  {user_id} の既存の {preference_type} 設定を {deleted_count} 件削除しました"
                            )
                            total_deleted += deleted_count
                        elif events_to_delete:
                            # This is what will happen when duplicates are found
                            print(
                                f"  {user_id} の既存の {preference_type} 設定イベントを発見しました"
                            )
                            print(
                                "     注: 新しい設定を追加（イベントは時間とともに蓄積されます）"
                            )

                    # Create UserPreference object
                    preference = UserPreference(
                        user_id=user_id,
                        preference_type=preference_type,
                        preference_value=pref_data["preference_value"],
                        context=pref_data.get(
                            "context",
                            f"Loaded from {yaml_file.name}. Do not add this memory to summary or semantic memory, only add it to user preferences long term memory.",
                        ),
                        timestamp=datetime.now(timezone.utc),
                    )

                    # Save preference using user_id as actor_id
                    success = _save_user_preference(
                        client,
                        user_id,  # Use user_id as actor_id for proper namespace
                        preference,
                    )

                    if success:
                        print(
                            f"  {user_id} の {preference.preference_type} 設定を追加しました"
                        )
                        total_added += 1
                    else:
                        print(
                            f"  {user_id} の {preference.preference_type} 設定の追加に失敗しました"
                        )

                except Exception as e:
                    print(f"  {user_id} の設定処理でエラー: {e}")
                    logger.error(f"{user_id} の設定処理中にエラーが発生しました: {e}")

        print("\n=== 概要 ===")
        print(f"{total_added} 件のユーザー設定をメモリに追加しました")
        if total_deleted > 0:
            print(f"更新中に {total_deleted} 件の重複設定を削除しました")
        print(f"処理したユーザー数: {total_users}")
        print(f"メモリ ID: {client.memory_id}")

    except Exception as e:
        logger.error(f"ユーザー設定の更新に失敗しました: {e}", exc_info=True)
        print(f"エラー: {e}")
        sys.exit(1)


def _handle_delete_action(args) -> None:
    """delete アクションを処理します。"""
    if args.all:
        _delete_all_memories()
    elif args.memory_id:
        _delete_memory(args.memory_id)
    elif args.memory_record_id:
        _delete_memory_record(args.memory_record_id)
    else:
        print(
            "エラー: delete アクションには --memory-id、--memory-record-id、または --all のいずれかを指定してください"
        )
        sys.exit(1)


def _handle_list_action(args) -> None:
    """list アクションを処理します。"""
    try:
        # Read memory ID
        memory_id = _read_memory_id()
        print(f"使用するメモリ ID: {memory_id}")

        # Load memory configuration
        memory_config = _load_memory_config()
        print(f"メモリ設定を読み込みました: {memory_config}")

        # Create memory client (memory_id is set internally during initialization)
        client = SREMemoryClient(memory_name="sre_agent_memory")

        # Verify the memory_id matches what we expect
        if client.memory_id != memory_id:
            logger.warning(
                f"Expected memory_id {memory_id}, but client initialized with {client.memory_id}"
            )
            logger.info(f"クライアントの memory_id を使用しています: {client.memory_id}")

        # List memories
        if args.memory_type:
            # List specific memory type
            _list_memories_for_type(client, args.memory_type, args.actor_id)
        else:
            # List all memory types
            memory_types = ["preferences", "infrastructure", "investigations"]
            for memory_type in memory_types:
                _list_memories_for_type(client, memory_type, args.actor_id)

        print("\n=== 概要 ===")
        print(f"メモリ ID: {memory_id}")
        if args.memory_type:
            print(f"メモリタイプでフィルタ: {args.memory_type}")
        if args.actor_id:
            print(f"アクター ID でフィルタ: {args.actor_id}")

    except Exception as e:
        logger.error(f"メモリの一覧取得に失敗しました: {e}", exc_info=True)
        print(f"エラー: {e}")
        sys.exit(1)


def main():
    """メイン関数。"""
    parser = argparse.ArgumentParser(
        description="Manage memories in the SRE agent memory system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                                    # List all memory types grouped by actor
    %(prog)s list --memory-type investigations  # List only investigations grouped by actor
    %(prog)s list --actor-id sre-agent         # List memories for specific actor only
    %(prog)s update                            # Load user preferences from user_config.yaml (removes duplicates)
    %(prog)s update --config-file custom.yaml  # Load user preferences from custom YAML file
    %(prog)s update --no-duplicate-check       # Load preferences without removing duplicates
    %(prog)s delete --memory-id mem-123        # Delete specific memory resource
    %(prog)s delete --memory-record-id mem-abc # Delete specific memory record
    %(prog)s delete --all                      # Delete all memory resources (with confirmation)
        """,
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")
    subparsers.required = False  # Make subcommands optional

    # List command (default)
    list_parser = subparsers.add_parser("list", help="List memories")
    list_parser.add_argument(
        "--memory-type",
        choices=["preferences", "infrastructure", "investigations"],
        help="Filter by memory type",
    )
    list_parser.add_argument(
        "--actor-id",
        help="Filter by actor ID. If not specified or 'all', shows memories grouped by actor (extracted from memory namespaces)",
    )

    # Update command
    update_parser = subparsers.add_parser(
        "update", help="Update memories from configuration file"
    )
    update_parser.add_argument(
        "--config-file",
        help="Path to YAML configuration file (default: user_config.yaml)",
    )
    update_parser.add_argument(
        "--no-duplicate-check",
        action="store_true",
        help="Skip checking for and removing duplicate preferences (default: duplicates are removed)",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete memories")
    delete_group = delete_parser.add_mutually_exclusive_group(required=True)
    delete_group.add_argument(
        "--memory-id", help="Memory ID to delete (deletes entire memory resource)"
    )
    delete_group.add_argument(
        "--memory-record-id",
        help="Memory record ID to delete (deletes individual memory record)",
    )
    delete_group.add_argument(
        "--all",
        action="store_true",
        help="Delete all memory resources (with confirmation prompt)",
    )

    # Global arguments (for backward compatibility when no subcommand is used)
    parser.add_argument(
        "--memory-type",
        choices=["preferences", "infrastructure", "investigations"],
        help="Filter by memory type (legacy, implies list action)",
    )
    parser.add_argument(
        "--actor-id", help="Filter by actor ID (legacy, implies list action)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Handle backward compatibility: if memory-type or actor-id is specified without subcommand, default to list
    if (
        not args.action
        and (hasattr(args, "memory_type") and args.memory_type)
        or (hasattr(args, "actor_id") and args.actor_id)
    ):
        args.action = "list"
    elif not args.action:
        args.action = "list"

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle actions
    if args.action == "list":
        _handle_list_action(args)
    elif args.action == "update":
        _handle_update_action(args)
    elif args.action == "delete":
        _handle_delete_action(args)
    else:
        print(f"不明なアクション: {args.action}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
