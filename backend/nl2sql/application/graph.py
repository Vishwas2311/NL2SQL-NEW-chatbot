"""Pure structural graph checks and the runtime traversal boundary."""

from collections import deque
from collections.abc import Iterable
from typing import Protocol


class GraphTraversal(Protocol):
    """An immutable certified topology, filtered before traversal."""

    def shortest_path(
        self,
        source: str,
        target: str,
        allowed: set[tuple[str, str]],
        excluded: tuple[str, str] | None = None,
    ) -> list[str]:
        """Return the shortest permitted route, or an empty list."""
        ...


class DirectedGraph:
    """Transient validation evidence; never a persistent runtime database."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, object]] = {}
        self.links: dict[tuple[str, str], dict[str, object]] = {}
        self.adjacency: dict[str, set[str]] = {}

    def __contains__(self, node: str) -> bool:
        return node in self.nodes

    def add_node(self, node: str, **attributes: object) -> None:
        """Retain isolated nodes for structural checks."""
        self.nodes.setdefault(node, {}).update(attributes)

    def add_nodes_from(self, nodes: Iterable[str]) -> None:
        """Register declared identifiers."""
        for node in nodes:
            self.add_node(node)

    def add_edge(self, source: str, target: str, **attributes: object) -> None:
        """Record directed dependencies."""
        self.add_nodes_from((source, target))
        self.links[source, target] = attributes
        self.adjacency.setdefault(source, set()).add(target)

    def successors(self, node: str) -> list[str]:
        """Return immediate dependencies in insertion order."""
        return sorted(self.adjacency.get(node, set()))

    def shortest_path(
        self,
        source: str,
        target: str,
        allowed: set[tuple[str, str]],
        excluded: tuple[str, str] | None = None,
    ) -> list[str]:
        """Linear breadth-first structural proof; empty means unreachable."""
        neighbors: dict[str, list[str]] = {}
        for left, right in self.links:
            if (left, right) in allowed and (left, right) != excluded:
                neighbors.setdefault(left, []).append(right)
        pending = deque([source])
        parents: dict[str, str | None] = {source: None}
        while pending:
            current = pending.popleft()
            if current == target:
                route = [target]
                while (parent := parents[route[-1]]) is not None:
                    route.append(parent)
                return list(reversed(route))
            for node in neighbors.get(current, []):
                if node not in parents:
                    parents[node] = current
                    pending.append(node)
        return []

    def acyclic(self) -> bool:
        """Kahn's algorithm avoids recursion limits on large metadata."""
        counts = dict.fromkeys(self.nodes, 0)
        adjacency: dict[str, list[str]] = {}
        for left, right in self.links:
            counts[right] += 1
            adjacency.setdefault(left, []).append(right)
        pending = [node for node, count in counts.items() if count == 0]
        visited = 0
        while pending:
            visited += 1
            for target in adjacency.get(pending.pop(), []):
                counts[target] -= 1
                if counts[target] == 0:
                    pending.append(target)
        return visited == len(counts)
