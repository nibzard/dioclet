"""Board graph, shortest paths, and site lookups.

The V0.1 board is a 5x5 orthogonal grid. Coordinates are [x, y] with
x, y in 0..4; y=0 is the north row. Neighbor tie-break order is
north, east, south, west so paths and searches are deterministic.
"""

from collections import deque

ENGINE_VERSION = "0.1.0"

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

    def in_bounds(self, cell):
        return 0 <= cell[0] < self.width and 0 <= cell[1] < self.height

    def neighbors(self, cell):
        """Adjacent cells in tie-break order (north, east, south, west)."""
        result = []
        for dx, dy in DIRECTIONS:
            nxt = (cell[0] + dx, cell[1] + dy)
            if self.in_bounds(nxt):
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
