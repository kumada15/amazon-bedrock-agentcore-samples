import json
from unittest.mock import Mock, patch

import pytest

from sre_agent.memory.client import SREMemoryClient
from sre_agent.memory.strategies import (
    InfrastructureKnowledge,
    InvestigationSummary,
    UserPreference,
)
from sre_agent.memory.tools import (
    RetrieveMemoryTool,
    SaveInfrastructureTool,
    SaveInvestigationTool,
    SavePreferenceTool,
)


class TestSavePreferenceTool:
    """SavePreferenceTool のテスト。"""

    @pytest.fixture
    def mock_client(self):
        """モック Memory クライアントを作成する。"""
        mock = Mock(spec=SREMemoryClient)
        return mock

    @pytest.fixture
    def save_preference_tool(self, mock_client):
        """モッククライアントで SavePreferenceTool を作成する。"""
        return SavePreferenceTool(mock_client)

    def test_save_preference_success(self, save_preference_tool, mock_client):
        """ユーザー設定の保存成功をテストする。"""
        with patch("sre_agent.memory.tools._save_user_preference") as mock_save:
            mock_save.return_value = True

            preference = UserPreference(
                user_id="user123",
                preference_type="escalation",
                preference_value={"contact": "ops@company.com"},
            )

            result = save_preference_tool._run(
                content=preference, context="test context", actor_id="sre-agent"
            )

            assert "Saved user preference: escalation for user user123" in result
            mock_save.assert_called_once()

    def test_save_preference_failure(self, save_preference_tool, mock_client):
        """ユーザー設定の保存失敗をテストする。"""
        with patch("sre_agent.memory.tools._save_user_preference") as mock_save:
            mock_save.return_value = False

            preference = UserPreference(
                user_id="user123",
                preference_type="escalation",
                preference_value={"contact": "ops@company.com"},
            )

            result = save_preference_tool._run(
                content=preference, context=None, actor_id="sre-agent"
            )

            assert "Failed to save user preference: escalation" in result


class TestSaveInfrastructureTool:
    """SaveInfrastructureTool のテスト。"""

    @pytest.fixture
    def mock_client(self):
        """モック Memory クライアントを作成する。"""
        mock = Mock(spec=SREMemoryClient)
        return mock

    @pytest.fixture
    def save_infrastructure_tool(self, mock_client):
        """モッククライアントで SaveInfrastructureTool を作成する。"""
        return SaveInfrastructureTool(mock_client)

    def test_save_infrastructure_success(self, save_infrastructure_tool, mock_client):
        """インフラストラクチャ知識の保存成功をテストする。"""
        with patch(
            "sre_agent.memory.tools._save_infrastructure_knowledge"
        ) as mock_save:
            mock_save.return_value = True

            knowledge = InfrastructureKnowledge(
                service_name="web-service",
                knowledge_type="dependency",
                knowledge_data={"depends_on": "database"},
            )

            result = save_infrastructure_tool._run(
                content=knowledge, context="test context", actor_id="sre-agent"
            )

            assert (
                "Saved infrastructure knowledge: dependency for web-service" in result
            )
            mock_save.assert_called_once()

    def test_save_infrastructure_failure(self, save_infrastructure_tool, mock_client):
        """インフラストラクチャ知識の保存失敗をテストする。"""
        with patch(
            "sre_agent.memory.tools._save_infrastructure_knowledge"
        ) as mock_save:
            mock_save.return_value = False

            knowledge = InfrastructureKnowledge(
                service_name="web-service",
                knowledge_type="dependency",
                knowledge_data={"depends_on": "database"},
            )

            result = save_infrastructure_tool._run(
                content=knowledge, context=None, actor_id="sre-agent"
            )

            assert "Failed to save infrastructure knowledge for web-service" in result


class TestSaveInvestigationTool:
    """SaveInvestigationTool のテスト。"""

    @pytest.fixture
    def mock_client(self):
        """モック Memory クライアントを作成する。"""
        mock = Mock(spec=SREMemoryClient)
        return mock

    @pytest.fixture
    def save_investigation_tool(self, mock_client):
        """モッククライアントで SaveInvestigationTool を作成する。"""
        return SaveInvestigationTool(mock_client)

    def test_save_investigation_success(self, save_investigation_tool, mock_client):
        """調査サマリーの保存成功をテストする。"""
        with patch("sre_agent.memory.tools._save_investigation_summary") as mock_save:
            mock_save.return_value = True

            summary = InvestigationSummary(
                incident_id="incident_123",
                query="Why is service down?",
                resolution_status="completed",
            )

            result = save_investigation_tool._run(
                content=summary, context="test context", actor_id="sre-agent"
            )

            assert "Saved investigation summary for incident incident_123" in result
            mock_save.assert_called_once()

    def test_save_investigation_failure(self, save_investigation_tool, mock_client):
        """調査サマリーの保存失敗をテストする。"""
        with patch("sre_agent.memory.tools._save_investigation_summary") as mock_save:
            mock_save.return_value = False

            summary = InvestigationSummary(
                incident_id="incident_123",
                query="Why is service down?",
                resolution_status="completed",
            )

            result = save_investigation_tool._run(
                content=summary, context=None, actor_id="sre-agent"
            )

            assert "Failed to save investigation summary for incident_123" in result


class TestRetrieveMemoryTool:
    """RetrieveMemoryTool のテスト。"""

    @pytest.fixture
    def mock_client(self):
        """モック Memory クライアントを作成する。"""
        mock = Mock(spec=SREMemoryClient)
        return mock

    @pytest.fixture
    def retrieve_tool(self, mock_client):
        """モッククライアントで RetrieveMemoryTool を作成する。"""
        return RetrieveMemoryTool(mock_client)

    def test_retrieve_preferences_success(self, retrieve_tool, mock_client):
        """ユーザー設定の取得成功をテストする。"""
        mock_preferences = [
            Mock(
                model_dump=Mock(
                    return_value={
                        "user_id": "user123",
                        "preference_type": "escalation",
                        "preference_value": {"contact": "ops@company.com"},
                    }
                )
            )
        ]

        with patch(
            "sre_agent.memory.tools._retrieve_user_preferences"
        ) as mock_retrieve:
            mock_retrieve.return_value = mock_preferences

            result = retrieve_tool._run(
                memory_type="preference",
                query="escalation contacts",
                actor_id="user123",
            )

            result_data = json.loads(result)
            assert len(result_data) == 1
            assert result_data[0]["user_id"] == "user123"
            mock_retrieve.assert_called_once_with(
                mock_client, "user123", "escalation contacts"
            )

    def test_retrieve_infrastructure_knowledge(self, retrieve_tool, mock_client):
        """インフラストラクチャ知識の取得をテストする。"""
        mock_knowledge = [
            Mock(
                model_dump=Mock(
                    return_value={
                        "service_name": "web-service",
                        "knowledge_type": "dependency",
                        "knowledge_data": {"depends_on": "database"},
                    }
                )
            )
        ]

        with patch(
            "sre_agent.memory.tools._retrieve_infrastructure_knowledge"
        ) as mock_retrieve:
            mock_retrieve.return_value = mock_knowledge

            result = retrieve_tool._run(
                memory_type="infrastructure",
                query="service dependencies",
                actor_id="sre-agent",
            )

            result_data = json.loads(result)
            assert len(result_data) == 1
            assert result_data[0]["service_name"] == "web-service"
            mock_retrieve.assert_called_once_with(
                mock_client, "sre-agent", "service dependencies"
            )

    def test_retrieve_investigation_summaries(self, retrieve_tool, mock_client):
        """調査サマリーの取得をテストする。"""
        mock_summaries = [
            Mock(
                model_dump=Mock(
                    return_value={
                        "incident_id": "incident_123",
                        "query": "Service down",
                        "resolution_status": "completed",
                    }
                )
            )
        ]

        with patch(
            "sre_agent.memory.tools._retrieve_investigation_summaries"
        ) as mock_retrieve:
            mock_retrieve.return_value = mock_summaries

            result = retrieve_tool._run(
                memory_type="investigation",
                query="service outage",
                actor_id="sre-agent",
                max_results=3,
            )

            result_data = json.loads(result)
            assert len(result_data) == 1
            assert result_data[0]["incident_id"] == "incident_123"
            mock_retrieve.assert_called_once_with(
                mock_client, "sre-agent", "service outage"
            )

    def test_retrieve_unknown_memory_type(self, retrieve_tool, mock_client):
        """不明な Memory タイプでの取得をテストする。"""
        result = retrieve_tool._run(
            memory_type="unknown", query="test query", actor_id="sre-agent"
        )

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Unknown memory type: unknown" in result_data["error"]
        assert "supported_types" in result_data

    def test_retrieve_memory_exception(self, retrieve_tool, mock_client):
        """取得中の例外処理をテストする。"""
        with patch(
            "sre_agent.memory.tools._retrieve_user_preferences"
        ) as mock_retrieve:
            mock_retrieve.side_effect = Exception("Database error")

            result = retrieve_tool._run(
                memory_type="preference", query="test query", actor_id="user123"
            )

            result_data = json.loads(result)
            assert "error" in result_data
            assert "Error retrieving preference memory" in result_data["error"]
