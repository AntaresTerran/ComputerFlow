from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def intersect(self, other: "Rect") -> "Rect | None":
        result = Rect(
            max(self.left, other.left),
            max(self.top, other.top),
            min(self.right, other.right),
            min(self.bottom, other.bottom),
        )
        return result if result.width > 0 and result.height > 0 else None

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def point(self, x: int, y: int) -> tuple[int, int]:
        """Map normalized image endpoints to physical pixel centers in this crop."""
        if not (0 <= x <= 1000 and 0 <= y <= 1000 and self.width > 0 and self.height > 0):
            raise ValueError("Koordinaten außerhalb des Bildausschnitts")
        return (
            self.left + round(x * (self.width - 1) / 1000),
            self.top + round(y * (self.height - 1) / 1000),
        )

    def normalized(self, x: int, y: int) -> tuple[int, int]:
        if not self.contains(x, y):
            raise ValueError("Punkt außerhalb des Bildausschnitts")
        return (
            round(1000 * (x - self.left) / max(1, self.width - 1)),
            round(1000 * (y - self.top) / max(1, self.height - 1)),
        )
