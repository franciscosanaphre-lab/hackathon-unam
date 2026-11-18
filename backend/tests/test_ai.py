"""Pruebas de IA con Bedrock simulado (sin red) + comprobaciones de seguridad."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.snapreverse.ai import agent
from backend.snapreverse.ai.bedrock import AIUnavailable, bedrock
from backend.snapreverse.ai.tools import Ctx, ToolError, run_tool
from backend.snapreverse.data_access import Tables
from backend.snapreverse.metrics import build_interventions
from backend.snapreverse.service import svc

NID, GID = 43298, 2021092611


@pytest.fixture(scope="module")
def client():
    tb = Tables()
    svc.inject(tb, build_interventions(tb))
    from backend.main import app
    return TestClient(app)


def args(**k):
    return {"player_id": NID, "game_id": GID, **k}


def test_tools_return_evidence(client):
    c = Ctx(svc, NID, GID, "live")
    r = run_tool(c, "get_player_performance", args())
    assert r["evidence_id"] == "E1" and r["n_comparables"] > 0
    r = run_tool(c, "investigate_performance_change", args())
    assert r["veredicto"] in ("estable", "marca_no_robusta", "evidencia_insuficiente", "caida_persistente_en_ambos_modos")
    r = run_tool(c, "find_relevant_plays", args(criteria="lowest_index"))
    assert r["jugadas"] and all(j["playId"] in c.known_plays for j in r["jugadas"])
    run_tool(c, "evaluate_available_alternatives", args())


def test_tool_validation(client):
    c = Ctx(svc, NID, GID, "live")
    for name, a in [("rm_rf", {}), ("get_player_performance", {"player_id": "1", "game_id": GID}),
                    ("get_player_performance", args(extra=1)), ("find_relevant_plays", args(criteria="x")),
                    ("get_player_performance", {"player_id": 1, "game_id": GID})]:
        with pytest.raises(ToolError):
            run_tool(c, name, a)


def test_compare_only_own_plays(client):
    c = Ctx(svc, NID, GID, "live")
    with pytest.raises(ToolError):
        run_tool(c, "compare_interventions", {"game_id": GID, "play_id_1": 1, "play_id_2": 2})


class FakeBedrock:
    """Primero pide herramienta, luego devuelve JSON con ids inventados que deben ser filtrados."""
    def __init__(self): self.n = 0
    def __call__(self, system, messages, tools=None, max_tokens=None):
        self.n += 1
        if self.n == 1:
            return {"stopReason": "tool_use", "output": {"message": {"role": "assistant", "content": [
                {"toolUse": {"toolUseId": "t1", "name": "get_player_performance", "input": args()}}]}}}
        rep = {"headline": "Estable", "findings": [{"text": "Índice mediano 999.9 yd/s", "evidence_ids": ["E1", "E99"]}],
               "interpretation": "x", "recommendations": [{"text": "Ver video", "evidence_ids": ["E1"]}], "limitations": ["l"],
               "referenced_play_ids": [123456789]}
        return {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": json.dumps(rep)}]}}}


def test_agent_filters_invented(client, monkeypatch):
    agent._cache.clear()
    monkeypatch.setattr(bedrock, "converse", FakeBedrock())
    r = client.post("/api/ai/analyze-player", json={"nflId": NID, "gameId": GID, "mode": "live"}).json()
    assert r["structured"] and r["referenced_play_ids"] == []                 # id inventado eliminado
    f = r["findings"][0]
    assert f["evidence_ids"] == ["E1"] and f["verified"] is False             # cifra 999.9 no sustentada
    assert "NaN" not in json.dumps(r)


def test_aws_error_does_not_break(client, monkeypatch):
    agent._cache.clear()
    def boom(*a, **k): raise AIUnavailable("ExpiredTokenException", "Las credenciales AWS expiraron")
    monkeypatch.setattr(bedrock, "converse", boom)
    r = client.post("/api/ai/chat", json={"nflId": NID, "gameId": GID, "message": "hola"})
    assert r.status_code == 503 and r.json()["ai_available"] is False
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get(f"/api/players/{NID}/games/{GID}/series").status_code == 200


def test_tool_loop_limit(client, monkeypatch):
    def always_tool(system, messages, tools=None, max_tokens=None):
        if tools is None:
            return {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": "fin"}]}}}
        return {"stopReason": "tool_use", "output": {"message": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": "x", "name": "get_player_performance", "input": args()}}]}}}
    monkeypatch.setattr(bedrock, "converse", always_tool)
    c = Ctx(svc, NID, GID, "live")
    text, calls = agent.run_agent(c, "q")
    assert len(calls) == agent.MAX_TOOL_CALLS and text == "fin"


def test_input_validation(client):
    assert client.post("/api/ai/chat", json={"nflId": NID, "gameId": GID, "message": ""}).status_code == 422
    assert client.post("/api/ai/chat", json={"nflId": NID, "gameId": GID, "message": "x" * 5000}).status_code == 422
    assert client.post("/api/ai/analyze-player", json={"nflId": 1, "gameId": 2}).status_code == 404
    assert client.post("/api/ai/analyze-player", json={"nflId": NID, "gameId": GID, "mode": "zz"}).status_code == 422


def test_no_credentials_in_tracked_files():
    root = Path(__file__).resolve().parents[2]
    pat = re.compile(r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|IQoJb3" + r"JpZ2lu")
    for f in list((root / "backend").rglob("*.py")) + list((root / "dashboard/src").rglob("*.ts*")) + list(root.glob("*.md")):
        assert not pat.search(f.read_text(errors="ignore")), f
    dist = root / "dashboard" / "dist"
    if dist.exists():
        for f in dist.rglob("*.js"):
            assert not pat.search(f.read_text(errors="ignore"))
