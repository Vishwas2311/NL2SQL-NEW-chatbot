"""Security-sensitive graph bounds survive the storage-engine migration."""

from nl2sql.application.catalog import _alternative_path
from nl2sql.application.graph import DirectedGraph


def test_unequal_alternatives_and_edge_budget():
    graph = DirectedGraph()
    for left, right in [("a", "b"), ("b", "z"), ("a", "c"), ("c", "d"), ("d", "z")]:
        graph.add_edge(left, right)
    allowed = set(graph.links)
    assert _alternative_path(graph, allowed, ["a", "b", "z"])
    # Seven edges are outside the approved alternative-path budget.
    graph = DirectedGraph()
    graph.add_edge("a", "z")
    route = ["a", "b", "c", "d", "e", "f", "g", "z"]
    for left, right in zip(route, route[1:], strict=False):
        graph.add_edge(left, right)
    assert not _alternative_path(graph, set(graph.links), ["a", "z"])
    assert graph.shortest_path("a", "z", set(graph.links), ("a", "z")) == route
    assert graph.acyclic()
    graph.add_edge("z", "a")
    assert not graph.acyclic()


def test_disconnected_cycle_and_large_chain():
    graph = DirectedGraph()
    for index in range(2000):
        graph.add_edge(str(index), str(index + 1))
    assert len(graph.shortest_path("0", "2000", set(graph.links))) == 2001
    assert graph.acyclic()
    graph.add_edge("isolated", "isolated")
    assert not graph.acyclic()
