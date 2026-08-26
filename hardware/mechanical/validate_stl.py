#!/usr/bin/env python3
"""Validate generated ASCII STL topology without third-party dependencies."""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

Vertex = tuple[float, float, float]
Facet = tuple[Vertex, Vertex, Vertex]
Edge = tuple[Vertex, Vertex]


def load_facets(path: Path) -> list[Facet]:
    facets: list[Facet] = []
    current: list[Vertex] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.strip().split()
        if fields[:1] == ["vertex"]:
            if len(fields) != 4:
                raise ValueError(f"{path}:{line_number}: malformed vertex")
            vertex = (float(fields[1]), float(fields[2]), float(fields[3]))
            if not all(math.isfinite(value) for value in vertex):
                raise ValueError(f"{path}:{line_number}: non-finite vertex")
            current.append(vertex)
        elif fields[:1] == ["endfacet"]:
            if len(current) != 3:
                raise ValueError(
                    f"{path}:{line_number}: facet has {len(current)} vertices, expected 3"
                )
            facets.append((current[0], current[1], current[2]))
            current = []
    if current:
        raise ValueError(f"{path}: unterminated facet")
    if not facets:
        raise ValueError(f"{path}: no facets found")
    return facets


def triangle_area_twice_squared(facet: Facet) -> float:
    a, b, c = facet
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return sum(value * value for value in cross)


def analyze(path: Path) -> list[str]:
    facets = load_facets(path)
    errors: list[str] = []
    valid_facets: list[int] = []
    edge_facets: defaultdict[Edge, list[tuple[int, Vertex, Vertex]]] = defaultdict(list)
    vertex_links: defaultdict[Vertex, defaultdict[Vertex, set[Vertex]]] = defaultdict(
        lambda: defaultdict(set)
    )

    for index, facet in enumerate(facets):
        if len(set(facet)) != 3 or triangle_area_twice_squared(facet) <= 1e-18:
            errors.append(f"facet {index + 1} is degenerate or collinear")
            continue
        valid_facets.append(index)
        a, b, c = facet
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (start, end) if start <= end else (end, start)
            edge_facets[edge].append((index, start, end))
        for center, left, right in ((a, b, c), (b, c, a), (c, a, b)):
            vertex_links[center][left].add(right)
            vertex_links[center][right].add(left)

    parent = list(range(len(facets)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    boundary_edges = 0
    nonmanifold_edges = 0
    orientation_errors = 0
    for records in edge_facets.values():
        if len(records) == 1:
            boundary_edges += 1
        elif len(records) > 2:
            nonmanifold_edges += 1
        if len(records) >= 2:
            for record in records[1:]:
                union(records[0][0], record[0])
        if len(records) == 2:
            first = records[0]
            second = records[1]
            if first[1] != second[2] or first[2] != second[1]:
                orientation_errors += 1

    components = {find(index) for index in valid_facets}
    if len(components) != 1:
        errors.append(f"mesh has {len(components)} edge-disconnected components")
    if boundary_edges:
        errors.append(f"mesh has {boundary_edges} boundary edges")
    if nonmanifold_edges:
        errors.append(f"mesh has {nonmanifold_edges} edges shared by more than two facets")
    if orientation_errors:
        errors.append(f"mesh has {orientation_errors} inconsistently directed paired edges")

    vertex_link_errors = 0
    for adjacency in vertex_links.values():
        neighbors = set(adjacency)
        if any(len(adjacency[neighbor]) != 2 for neighbor in neighbors):
            vertex_link_errors += 1
            continue
        pending = [next(iter(neighbors))]
        visited: set[Vertex] = set()
        while pending:
            neighbor = pending.pop()
            if neighbor in visited:
                continue
            visited.add(neighbor)
            pending.extend(adjacency[neighbor] - visited)
        if visited != neighbors:
            vertex_link_errors += 1
    if vertex_link_errors:
        errors.append(f"mesh has {vertex_link_errors} non-manifold vertex links")

    vertices = set(vertex_links)
    axes = list(zip(*vertices))
    bounds = tuple((min(axis), max(axis)) for axis in axes)
    print(
        f"{path}: facets={len(facets)} vertices={len(vertices)} components={len(components)} "
        f"boundary_edges={boundary_edges} nonmanifold_edges={nonmanifold_edges} "
        f"orientation_errors={orientation_errors} vertex_link_errors={vertex_link_errors} "
        f"bounds={bounds}"
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("meshes", nargs="+", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    for mesh in args.meshes:
        try:
            errors.extend(f"{mesh}: {error}" for error in analyze(mesh))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
    if errors:
        print(f"FAIL: {len(errors)} STL validation error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {len(args.meshes)} closed, connected, consistently wound 2-manifold mesh(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
