"""Porównanie przesłanego zdjęcia z kopią znalezioną w sieci.

Globalny hash percepcyjny nie wykrywa lokalnych zmian (doklejony obiekt zmienia pHash o 1–2 bity),
dlatego kopię dopasowujemy do zdjęcia (SIFT + transformacja podobieństwa, co obsługuje kadrowanie
i skalowanie), dopasowujemy jasność i kontrast kopii z pominięciem odstających pikseli (żeby sama
edycja nie przesunęła dopasowania), a potem porównujemy różnicę w siatce bloków. Lokalna edycja daje
kilka "gorących" bloków przy niskiej medianie; inna obróbka (filtr, kadr, skan) podnosi medianę wszędzie.
"""

from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
from PIL import Image

GRID = 8
_WORK_SIZE = 640
_MIN_GOOD_MATCHES = 12
_MIN_INLIERS = 10
_MIN_OVERLAP = 0.3
_MIN_CELL_COVERAGE = 0.7
# Progi w poziomach szarości (0–255), skalibrowane na kopiach z Yandex/TinEye: identyczne kopie
# mają medianę różnic ~0–2, wersje po innej obróbce 8–15, a doklejony obiekt lub napis >10 w bloku.
_VARIANT_MEDIAN = 8.0
_HOT_FLOOR = 10.0
_HOT_FACTOR = 4.0
_FIT_ROUNDS = 3
_FIT_KEEP_PERCENTILE = 85


class Relation(StrEnum):
    IDENTICAL = "identical"
    LOCALLY_MODIFIED = "locally_modified"
    DIFFERENT_VERSION = "different_version"
    NOT_COMPARABLE = "not_comparable"


@dataclass
class Comparison:
    relation: Relation
    median_diff: float | None = None
    hot_cells: list[tuple[int, int]] = field(default_factory=list)
    overlap: float | None = None


def prepare(img: Image.Image) -> np.ndarray:
    gray = img.convert("L")
    gray.thumbnail((_WORK_SIZE, _WORK_SIZE))
    return np.asarray(gray)


def _residual(query: np.ndarray, warped: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """|zdjęcie − (a·kopia + b)| po odpornym dopasowaniu a, b (kompresja, kontrast, jasność)."""
    q = cv2.GaussianBlur(query.astype(np.float32), (0, 0), 2)
    c = cv2.GaussianBlur(warped.astype(np.float32), (0, 0), 2)
    selected = mask
    a, b = 1.0, 0.0
    for _ in range(_FIT_ROUNDS):
        if c[selected].std() < 1.0:
            a, b = 1.0, float(np.median(q[selected] - c[selected]))
        else:
            a, b = np.polyfit(c[selected], q[selected], 1)
        residual = np.abs(q - (a * c + b))
        selected = mask & (residual <= np.percentile(residual[mask], _FIT_KEEP_PERCENTILE))
    return np.abs(q - (a * c + b))


def compare(query: np.ndarray, candidate: np.ndarray) -> Comparison:
    """Oba argumenty z `prepare`. Wynik opisuje kopię względem przesłanego zdjęcia."""
    sift = cv2.SIFT_create(nfeatures=1500)
    kq, dq = sift.detectAndCompute(query, None)
    kc, dc = sift.detectAndCompute(candidate, None)
    if dq is None or dc is None or len(kq) < _MIN_GOOD_MATCHES or len(kc) < _MIN_GOOD_MATCHES:
        return Comparison(Relation.NOT_COMPARABLE)

    pairs = cv2.BFMatcher().knnMatch(dc, dq, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < _MIN_GOOD_MATCHES:
        return Comparison(Relation.NOT_COMPARABLE)

    src = np.float32([kc[m.queryIdx].pt for m in good])
    dst = np.float32([kq[m.trainIdx].pt for m in good])
    transform, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if transform is None or inliers is None or int(inliers.sum()) < _MIN_INLIERS:
        return Comparison(Relation.NOT_COMPARABLE)

    h, w = query.shape
    warped = cv2.warpAffine(candidate, transform, (w, h))
    mask = cv2.warpAffine(np.full(candidate.shape, 255, np.uint8), transform, (w, h))
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8)) > 0
    overlap = float(mask.mean())
    if overlap < _MIN_OVERLAP:
        return Comparison(Relation.NOT_COMPARABLE, overlap=overlap)

    diff = _residual(query, warped, mask)
    cells: dict[tuple[int, int], float] = {}
    for i in range(GRID):
        for j in range(GRID):
            rows = slice(i * h // GRID, (i + 1) * h // GRID)
            cols = slice(j * w // GRID, (j + 1) * w // GRID)
            cell_mask = mask[rows, cols]
            if cell_mask.mean() >= _MIN_CELL_COVERAGE:
                cells[(i, j)] = float(diff[rows, cols][cell_mask].mean())
    if not cells:
        return Comparison(Relation.NOT_COMPARABLE, overlap=overlap)

    median = float(np.median(list(cells.values())))
    if median > _VARIANT_MEDIAN:
        return Comparison(Relation.DIFFERENT_VERSION, median_diff=median, overlap=overlap)
    threshold = max(_HOT_FLOOR, _HOT_FACTOR * median)
    hot = sorted(cell for cell, value in cells.items() if value > threshold)
    relation = Relation.LOCALLY_MODIFIED if hot else Relation.IDENTICAL
    return Comparison(relation, median_diff=median, hot_cells=hot, overlap=overlap)
