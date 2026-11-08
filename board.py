"""Board graph, shortest paths, and site lookups.

The board is an orthogonal grid. Coordinates are [x, y]; y=0 is the
north row. Neighbor tie-break order is north, east, south, west so
paths and searches are deterministic. An optional `board.blocked`
list removes cells from the graph (building interiors on the V0.6
real-board map); movement, duels, and paths use street cells only.
"""

from collections import deque

ENGINE_VERSION = "0.1.1"

# Direction order for tie-breaks: north, east, south, west.
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))
DIRECTION_NAMES = ("north", "east", "south", "west")


def cell_key(cell):
    return (cell[0], cell[1])


class Board:
    """Graph view over the grid defined by a validated rules dict."""

    def __init__(self, rules):
        board = rules["board"]
        self.width = board["width"]
        self.height = board["height"]
        self.gates = {p: tuple(c) for p, c in board["gates"].items()}
        self.districts = {name: tuple(c) for name, c in board["districts"].items()}
        self.district_at = {tuple(c): name for name, c in self.districts.items()}
        self.checkpoint = tuple(board["checkpoint"])
        self.glory_posts = [tuple(c) for c in board["glory_posts"]]
        sites = board["level2_sites"]
        self.level2_sites = {name: tuple(c) for name, c in sites.items()}
        self.seal_sites = {
            "cellars": self.level2_sites["cellars"],
            "guard_barracks": self.level2_sites["guard_barracks"],
            "peristyle": self.level2_sites["peristyle"],
        }
        self.seal_site_at = {cell: name for name, cell in self.seal_sites.items()}
        self.emperor = self.level2_sites["emperor"]
        self.retreat = self.level2_sites["retreat"]
        self.blocked = {tuple(c) for c in board.get("blocked", [])}

    def in_bounds(self, cell):
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def neighbors(self, cell):
        """Adjacent cells in tie-break order (north, east, south, west)."""
        result = []
        for dx, dy in DIRECTIONS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if self.in_bounds(nxt) and nxt not in self.blocked:
                result.append(nxt)
        return result

    def distances(self, start):
        """BFS shortest-path distances from start to every cell."""
        start = tuple(start)
        dist = {start: 0}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for nxt in self.neighbors(cur):
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1
                    queue.append(nxt)
        return dist

    def distance(self, a, b):
        return self.distances(a)[tuple(b)]

    def path(self, start, dest):
        """Deterministic shortest path from start to dest inclusive.

        Walks from start toward dest, taking the first neighbor in
        tie-break order that reduces the shortest-path distance.
        """
        start, dest = tuple(start), tuple(dest)
        if start == dest:
            return [start]
        dist_to_dest = self.distances(dest)
        if start not in dist_to_dest:
            raise ValueError(f"no path from {start} to {dest}")
        path = [start]
        cur = start
        while cur != dest:
            for nxt in self.neighbors(cur):
                if dist_to_dest.get(nxt, dist_to_dest[cur]) < dist_to_dest[cur]:
                    cur = nxt
                    break
            path.append(cur)
        return path


def validate_six_block_layout(rules):
    """Check the playable geometry, not only six declared rectangles.

    Generators use this check for the adopted six-block layout. Old
    rules remain available for replay without applying this contract.
    """
    b = Board(rules)
    remaining = set(b.blocked)
    components = []
    while remaining:
        start = remaining.pop()
        group = {start}
        queue = [start]
        for x, y in queue:
            for dx, dy in DIRECTIONS:
                adjacent = (x + dx, y + dy)
                if adjacent in remaining:
                    remaining.remove(adjacent)
                    group.add(adjacent)
                    queue.append(adjacent)
        components.append(frozenset(group))
    if len(components) != 6:
        raise ValueError(f"expected six intact blocks, found {len(components)}")

    buildings = rules["board"].get("buildings", [])
    if len(buildings) != 6:
        raise ValueError("expected six declared block footprints")
    footprints = []
    assigned = []
    for building in buildings:
        cells = frozenset((x, y)
                          for x in range(building["x0"], building["x1"] + 1)
                          for y in range(building["y0"], building["y1"] + 1))
        if not cells <= b.blocked:
            raise ValueError(f"street crosses block {building['name']}")
        footprints.append(cells)
        district = building.get("district")
        if district not in b.districts:
            raise ValueError(f"block {building['name']} needs its own district")
        assigned.append(district)
        ex, ey = b.districts[district]
        if not any((ex + dx, ey + dy) in cells for dx, dy in DIRECTIONS):
            raise ValueError(f"district {district} does not enter its block")
    if set(footprints) != set(components):
        raise ValueError("declared footprints must match the six physical blocks")
    if len(set(assigned)) != 6 or set(assigned) != set(b.districts):
        raise ValueError("each block needs exactly one distinct district")

    streets = rules["board"]["streets"]
    cardo, decumanus = streets["cardo"], streets["decumanus"]
    if cardo["axis"] != "north-south" or decumanus["axis"] != "east-west":
        raise ValueError("cardo must run north-south; decumanus must run east-west")
    cx, dy = cardo["coordinate"], decumanus["coordinate"]
    main_streets = {(cx, y) for y in range(b.height)} | {(x, dy) for x in range(b.width)}
    if main_streets & b.blocked:
        raise ValueError("main streets must run continuously between their gates")
    expected_gates = {"P0": (cx, 0), "P1": (b.width - 1, dy),
                      "P2": (cx, b.height - 1), "P3": (0, dy)}
    if b.gates != expected_gates or b.checkpoint != (cx, dy):
        raise ValueError("gates must end the main streets; checkpoint must mark their crossing")
