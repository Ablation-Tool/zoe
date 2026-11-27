"""Synthetic 3D teaching space inspired by LSI imaging and Dorothy's geometry."""
from dataclasses import dataclass
from fractions import Fraction
from html import escape
import math
from typing import List, Tuple


def spatial_piecewise_profile(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError("profile input must be a finite bounded number")
    if value <= -3:
        result, branch = 0, "zero-low"
    elif value < -2:
        result, branch = value ** 3, "cubic"
    elif value <= 2:
        result, branch = value ** 2, "quadratic"
    elif value < 3:
        result, branch = value, "linear"
    else:
        result, branch = 0, "zero-high"
    return {
        "value": result,
        "branch": branch,
        "source": "MATLAB Numerical Calculations, chapter 6, exercise 6-6 fixed piecewise profile",
        "clinical_claim": False,
    }


def collagen_mesh_scaling_review():
    observations = []
    for concentration, measured in ((0.5, 27.8), (1.0, 12.1), (2.0, 8.3)):
        predicted = 8.3 * math.sqrt(2.0 / concentration)
        observations.append({
            "concentration_mg_ml": concentration,
            "measured_mesh_um": measured,
            "simple_scaling_mesh_um": predicted,
            "residual_um": measured - predicted,
        })
    return {
        "observations": observations,
        "scaling_model": "mesh(c) = 8.3 um * sqrt((2 mg/ml) / c)",
        "interpretation": "The 0.5 mg/ml measurement deviates by 11.2 um; do not infer a universal concentration-scaling law.",
        "source": "Kaufman et al. 2005, doi:10.1529/biophysj.105.061994; Biomedical Imaging Principles chapter 10",
        "primary_source": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1366562/",
        "raw_images_analyzed": False,
        "clinical_claim": False,
    }


def matrix_layout_review(matrix):
    if not isinstance(matrix, (list, tuple)) or not 1 <= len(matrix) <= 8:
        raise ValueError("matrix requires 1 to 8 rows")
    if any(not isinstance(row, (list, tuple)) or not 1 <= len(row) <= 8 for row in matrix):
        raise ValueError("matrix rows require 1 to 8 columns")
    columns = len(matrix[0])
    if any(len(row) != columns for row in matrix):
        raise ValueError("matrix must be rectangular")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or abs(value) > 1e12
           for row in matrix for value in row):
        raise ValueError("matrix values must be finite bounded numbers")
    exact = [[Fraction(str(value)) for value in row] for row in matrix]
    square = len(matrix) == columns
    determinant = None
    if square:
        work = [row[:] for row in exact]
        determinant = Fraction(1)
        for column in range(columns):
            pivot = next((row for row in range(column, columns) if work[row][column]), None)
            if pivot is None:
                determinant = Fraction(0)
                break
            if pivot != column:
                work[column], work[pivot] = work[pivot], work[column]
                determinant = -determinant
            pivot_value = work[column][column]
            determinant *= pivot_value
            for row in range(column + 1, columns):
                factor = work[row][column] / pivot_value
                for index in range(column + 1, columns):
                    work[row][index] -= factor * work[column][index]
    singular = determinant == 0 if square else None
    if not square:
        inversion = "not applicable to a rectangular matrix"
    elif singular:
        inversion = "refused: zero determinant"
    else:
        inversion = "not computed; a nonzero determinant does not establish numerical conditioning"
    return {
        "shape": [len(matrix), columns],
        "transpose": [list(row) for row in zip(*matrix)],
        "diagonal": [matrix[index][index] for index in range(min(len(matrix), columns))],
        "column_major": [matrix[row][column] for column in range(columns) for row in range(len(matrix))],
        "square": square,
        "determinant": None if determinant is None else int(determinant) if determinant.denominator == 1 else float(determinant),
        "singular": singular,
        "inversion": inversion,
        "source": "MATLAB Numerical Calculations, chapter 4, matrix layout and exact-decimal determinant review",
        "clinical_claim": False,
    }


@dataclass(frozen=True)
class Volume:
    width: int
    depth: int
    height: int
    values: Tuple[float, ...]
    source: str = "Synthetic Neurogarden spatial bench; no patient or atlas-registration claim"

    def __post_init__(self):
        if not 1 <= self.width <= 16 or not 1 <= self.depth <= 16 or not 1 <= self.height <= 16:
            raise ValueError("volume dimensions must be between 1 and 16 voxels")
        if len(self.values) != self.width * self.depth * self.height:
            raise ValueError("voxel count does not match dimensions")
        if any(not math.isfinite(value) or value < 0 for value in self.values):
            raise ValueError("voxel values must be finite and nonnegative")

    def index(self, x, y, z):
        return x + self.width * (y + self.depth * z)

    def at(self, x, y, z):
        return self.values[self.index(x, y, z)]

    def replace(self, x, y, z, value):
        values = list(self.values)
        values[self.index(x, y, z)] = value
        return Volume(self.width, self.depth, self.height, tuple(values), self.source)


def sphere(diameter=7, intensity=1.0):
    if not 1 <= diameter <= 16 or not 0 < intensity <= 1e6:
        raise ValueError("invalid synthetic sphere")
    center = (diameter - 1) / 2
    radius = diameter / 2
    values = []
    for z in range(diameter):
        for y in range(diameter):
            for x in range(diameter):
                distance = math.sqrt((x - center) ** 2 + (y - center) ** 2 + (z - center) ** 2)
                values.append(float(intensity) if distance <= radius else 0.0)
    return Volume(diameter, diameter, diameter, tuple(values))


def kernel(sigma):
    if not 0 < sigma <= 3:
        raise ValueError("sigma must be between zero and three voxels")
    radius = max(1, math.ceil(3 * sigma))
    values = [math.exp(-(offset ** 2) / (2 * sigma ** 2)) for offset in range(-radius, radius + 1)]
    total = sum(values)
    return [value / total for value in values]


def convolve(volume, sigma):
    weights = kernel(sigma)
    radius = len(weights) // 2
    result = volume
    for axis in range(3):
        values = [0.0] * len(result.values)
        for z in range(result.height):
            for y in range(result.depth):
                for x in range(result.width):
                    total = 0.0
                    for offset, weight in zip(range(-radius, radius + 1), weights):
                        coordinates = [x, y, z]
                        coordinates[axis] += offset
                        if 0 <= coordinates[axis] < (result.width, result.depth, result.height)[axis]:
                            total += result.at(*coordinates) * weight
                    values[result.index(x, y, z)] = total
        result = Volume(result.width, result.depth, result.height, tuple(values), result.source)
    return result


def average_pool(volume, factor=2):
    if not 1 <= factor <= 16:
        raise ValueError("pooling factor must be between 1 and 16")
    width = math.ceil(volume.width / factor)
    depth = math.ceil(volume.depth / factor)
    height = math.ceil(volume.height / factor)
    values = []
    for z in range(height):
        for y in range(depth):
            for x in range(width):
                samples = []
                for dz in range(factor):
                    for dy in range(factor):
                        for dx in range(factor):
                            source = (x * factor + dx, y * factor + dy, z * factor + dz)
                            if source[0] < volume.width and source[1] < volume.depth and source[2] < volume.height:
                                samples.append(volume.at(*source))
                values.append(sum(samples) / (factor ** 3))
    return Volume(width, depth, height, tuple(values), volume.source)


def project(volume, axis="z"):
    if axis not in {"x", "y", "z"}:
        raise ValueError("projection axis must be x, y, or z")
    if axis == "z":
        rows, columns = volume.depth, volume.width
    elif axis == "y":
        rows, columns = volume.height, volume.width
    else:
        rows, columns = volume.height, volume.depth
    projected = []
    for row in range(rows):
        line = []
        for column in range(columns):
            if axis == "z":
                values = [volume.at(column, row, z) for z in range(volume.height)]
            elif axis == "y":
                values = [volume.at(column, y, row) for y in range(volume.depth)]
            else:
                values = [volume.at(x, row, column) for x in range(volume.width)]
            line.append(sum(values))
        projected.append(line)
    return projected


def recovery_coefficient(original, measured):
    if original.width != measured.width or original.depth != measured.depth or original.height != measured.height:
        raise ValueError("recovery comparison requires matching dimensions")
    truth = max(original.values)
    if truth <= 0:
        raise ValueError("recovery requires a nonempty original volume")
    return max(measured.values) / truth


def projection_svg(projected, title="Neurogarden projection"):
    if not projected or not projected[0] or any(len(row) != len(projected[0]) for row in projected):
        raise ValueError("projection must be a nonempty rectangular matrix")
    maximum = max(max(row) for row in projected)
    if maximum <= 0:
        raise ValueError("projection has no positive intensity")
    cell = max(4, min(24, 256 // max(len(projected[0]), len(projected))))
    width = len(projected[0]) * cell
    height = len(projected) * cell
    safe_title = escape(title)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 32}" height="{height + 64}" viewBox="0 0 {width + 32} {height + 64}" role="img" aria-label="{safe_title}">',
        '<rect width="100%" height="100%" fill="#080d18"/>',
        f'<text x="16" y="24" fill="#67e8f9" font-family="monospace" font-size="12">{safe_title}</text>',
    ]
    for y, row in enumerate(projected):
        for x, value in enumerate(row):
            ratio = min(1.0, max(0.0, value / maximum))
            red = round(20 + 216 * ratio)
            green = round(232 - 181 * ratio)
            blue = round(249 - 170 * ratio)
            parts.append(f'<rect x="{16 + x * cell}" y="{40 + y * cell}" width="{cell}" height="{cell}" fill="rgb({red},{green},{blue})"/>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"
