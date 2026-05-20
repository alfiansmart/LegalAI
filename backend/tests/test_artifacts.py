"""Tests for the artifact collector and builders."""
import pytest

from backend.agents import artifacts as A


def test_emit_validates_type():
    c = A.ArtifactCollector()
    with pytest.raises(ValueError):
        c.emit("unknown_type", "title", {})


def test_emit_preserves_order():
    c = A.ArtifactCollector()
    c.emit("mermaid", "first", {"source": "graph LR"})
    c.emit("table", "second", {"columns": [], "rows": []})
    items = c.to_list()
    assert [i["title"] for i in items] == ["first", "second"]


def test_builders_return_renderable_dicts():
    table_dict = A.table("X", ["A", "B"], [[1, 2], [3, 4]])
    assert table_dict["type"] == "table"
    assert table_dict["data"]["columns"] == ["A", "B"]
    assert table_dict["data"]["rows"] == [[1, 2], [3, 4]]

    timeline_dict = A.timeline("T", [{"year": 2020, "label": "Enacted"}])
    assert timeline_dict["data"]["events"][0]["label"] == "Enacted"

    diff_dict = A.diff("D", "old", "new")
    assert diff_dict["data"]["base"] == "old"
    assert diff_dict["data"]["head"] == "new"


def test_extend_accepts_builder_dicts():
    c = A.ArtifactCollector()
    c.extend(
        [
            A.mermaid("g", "graph LR\nA-->B"),
            A.table("t", ["a"], [[1]]),
        ]
    )
    assert len(c) == 2
    assert c.to_list()[0]["type"] == "mermaid"
    assert c.to_list()[1]["type"] == "table"
