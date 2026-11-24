"""The tools' output schemas are a contract with every client that listed them: a live agent keeps the schema it read
when it connected, so a changed shape fails each call it makes (2026-11-24: a deploy unwrapped every result and the
Reach's minds got "data/result must be object" from guide and act until they reconnected)."""

import asyncio

from embody.mcp_server import build_server
from embody.ops import Engine


def schemas(tmp_path):
    eng = Engine(tmp_path / "e.db")
    srv = build_server(eng.session("probe"), tmp_path / "e.db", engine=eng)
    return srv, {t.name: t.output_schema for t in asyncio.run(srv.list_tools())}


def structured(r):
    return getattr(r, "structured_content", None) or getattr(r, "structuredContent", None)


def test_a_tools_answer_stays_wrapped_in_result_as_clients_listed_it(tmp_path):
    srv, out = schemas(tmp_path)
    for name in ("guide", "act", "perceive", "join", "say"):
        assert out[name]["required"] == ["result"] and out[name]["properties"]["result"]["type"] == "object", name
    r = asyncio.run(srv.call_tool("guide", {"topic": "mind"}))
    assert set(structured(r)) == {"result"} and isinstance(structured(r)["result"], dict)


def test_a_tool_that_answers_with_a_list_may_answer_a_refusal_too(tmp_path):
    srv, out = schemas(tmp_path)
    kinds = {x.get("type") for x in out["find"]["properties"]["result"]["anyOf"]}
    assert kinds >= {"array", "object"}
    r = asyncio.run(srv.call_tool("find", {"name": "x"}))  # no world chosen: a refusal, inside the schema
    assert structured(r)["result"]["ok"] is False
