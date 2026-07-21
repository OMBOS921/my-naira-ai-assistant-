"""
DependencyGraph — Directed Acyclic Graph for capability dependencies.

07_Module_Design.md §1.A — dependency validation.
"""

from __future__ import annotations

from collections import defaultdict


class DependencyGraph:
    """Directed Acyclic Graph managing capability dependency edges.

    Each node represents a registered capability.  Edges go from a
    capability to its dependencies (the things it needs).

    Parameters
    ----------
    nodes : dict[str, set[str]] | None
        Pre-populated node set (used internally for copy).
    """

    def __init__(self, nodes: dict[str, set[str]] | None = None) -> None:
        self._nodes: dict[str, set[str]] = nodes if nodes is not None else {}
        self._dependents: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Graph mutation
    # ------------------------------------------------------------------

    def add_node(self, name: str, dependencies: tuple[str, ...]) -> None:
        """Register a node and its outgoing dependency edges.

        Parameters
        ----------
        name : str
            Capability name.
        dependencies : tuple[str, ...]
            Capabilities this node depends on.

        Raises
        ------
        ValueError
            If a node with *name* already exists.
        """
        if name in self._nodes:
            msg = f"DependencyGraph node already exists: {name}"
            raise ValueError(msg)
        self._nodes[name] = set(dependencies)
        for dep in dependencies:
            self._dependents[dep].add(name)

    def remove_node(self, name: str) -> None:
        """Remove a node and all its edges.

        Parameters
        ----------
        name : str
            Capability name.

        Raises
        ------
        KeyError
            If the node does not exist.
        """
        if name not in self._nodes:
            msg = f"DependencyGraph node not found: {name}"
            raise KeyError(msg)
        deps = self._nodes.pop(name)
        for dep in deps:
            self._dependents[dep].discard(name)
        self._dependents.pop(name, None)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def has_node(self, name: str) -> bool:
        """Return ``True`` if the node exists in the graph."""
        return name in self._nodes

    def get_dependencies(self, name: str) -> frozenset[str]:
        """Return the dependency set for a node.

        Raises ``KeyError`` if the node does not exist.
        """
        if name not in self._nodes:
            msg = f"DependencyGraph node not found: {name}"
            raise KeyError(msg)
        return frozenset(self._nodes[name])

    def get_dependents(self, name: str) -> frozenset[str]:
        """Return the set of nodes that depend on *name*."""
        return frozenset(self._dependents.get(name, set()))

    @property
    def is_empty(self) -> bool:
        """Return ``True`` if no nodes are registered."""
        return len(self._nodes) == 0

    @property
    def node_count(self) -> int:
        """Return the number of registered nodes."""
        return len(self._nodes)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Validate the graph for cycles and missing references.

        Returns a list of error messages (empty if the graph is valid).
        """
        errors: list[str] = []

        # Check for missing references (dependencies not in graph)
        for name, deps in self._nodes.items():
            for dep in deps:
                if dep not in self._nodes:
                    errors.append(
                        f"Capability '{name}' depends on unknown "
                        f"capability '{dep}'"
                    )

        # Check for cycles using DFS
        cycle_nodes = self._find_cycles()
        for node in cycle_nodes:
            errors.append(
                f"Circular dependency detected involving '{node}'"
            )

        return errors

    def can_enable(self, name: str, enabled: set[str]) -> tuple[bool, list[str]]:
        """Check whether a capability can be enabled.

        A capability can be enabled when all of its dependencies are
        already enabled.

        Parameters
        ----------
        name : str
            Capability to check.
        enabled : set[str]
            Set of currently enabled capabilities.

        Returns
        -------
        tuple[bool, list[str]]
            (True, []) if enable is allowed;
            (False, [missing_dep, ...]) if dependencies are unsatisfied.
        """
        if name not in self._nodes:
            return True, []
        deps = self._nodes[name]
        missing = [d for d in deps if d not in enabled]
        if missing:
            return False, missing
        return True, []

    def can_disable(self, name: str, enabled: set[str]) -> tuple[bool, list[str]]:
        """Check whether a capability can be disabled.

        A capability can be disabled when no enabled capability
        depends on it.

        Parameters
        ----------
        name : str
            Capability to check.
        enabled : set[str]
            Set of currently enabled capabilities.

        Returns
        -------
        tuple[bool, list[str]]
            (True, []) if disable is allowed;
            (False, [dependent, ...]) if dependents would break.
        """
        dependents = self._dependents.get(name, set())
        blocking = [d for d in dependents if d in enabled]
        if blocking:
            return False, blocking
        return True, []

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def topological_sort(self) -> list[str]:
        """Return capabilities in dependency order using Kahn's algorithm.

        Raises ``ValueError`` if the graph contains cycles.
        """
        in_degree: dict[str, int] = {n: 0 for n in self._nodes}
        adjacency: dict[str, list[str]] = {n: [] for n in self._nodes}

        for name, deps in self._nodes.items():
            for dep in deps:
                if dep in self._nodes:
                    in_degree[name] += 1
                    adjacency[dep].append(name)

        queue = [n for n, d in in_degree.items() if d == 0]
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbour in adjacency[node]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(result) != len(self._nodes):
            msg = "Circular dependency detected in topological sort"
            raise ValueError(msg)

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_cycles(self) -> set[str]:
        """Return set of node names involved in any cycle (DFS)."""
        visited: set[str] = set()
        recursion_stack: set[str] = set()
        cycle_nodes: set[str] = set()

        def _dfs(node: str) -> None:
            visited.add(node)
            recursion_stack.add(node)
            for dep in self._nodes.get(node, set()):
                if dep not in self._nodes:
                    continue
                if dep not in visited:
                    _dfs(dep)
                elif dep in recursion_stack:
                    cycle_nodes.add(node)
                    cycle_nodes.add(dep)
            recursion_stack.discard(node)

        for node in self._nodes:
            if node not in visited:
                _dfs(node)

        return cycle_nodes
