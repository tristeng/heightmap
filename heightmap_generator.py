import argparse
import json
import os
import requests
from typing import Any
import numpy as np
import OpenEXR
from scipy import interpolate
import re

URL_TEMPLATE = "https://deaddropgames.com/stuntski/api/levels/{id}"


def parse_polyline_from_json(json_data: dict[str, Any]) -> np.ndarray:
    """
    Extract polyline points from JSON data.

    Args:
        json_data: Dictionary containing JSON data with polyline information

    Returns:
        np.ndarray: Array of (x,y) coordinates
    """
    # Extract the points from the first polyline
    points_data: list[dict[str, float]] = json_data["polyLines"][0]["points"]

    # Convert to list of (x,y) coordinates
    points: list[tuple[float, float]] = [
        (point.get("x", 0.0), point.get("y", 0.0)) for point in points_data
    ]

    return np.array(points)


def read_polyline(file_path: str) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Read polyline data from JSON file.

    The JSON is expected to have a "polyLines" array where the first element
    has a "points" array containing objects with "x" and "y" attributes.

    Args:
        file_path: Path to the JSON file

    Returns:
        tuple: (np.ndarray: Array of (x,y) coordinates, dict: JSON data)
    """
    with open(file_path, "r") as f:
        json_data: dict[str, Any] = json.load(f)

    return parse_polyline_from_json(json_data), json_data


def fetch_polyline_from_url(id: int) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Fetch polyline data from a URL using an ID parameter.

    Args:
        id: ID to insert into the URL template

    Returns:
        tuple: (np.ndarray: Array of (x,y) coordinates, dict: JSON data)
    """
    url = URL_TEMPLATE.format(id=id)
    print(f"Fetching data from {url}...")

    response = requests.get(url)
    response.raise_for_status()  # Raise an exception if request failed

    json_data: dict[str, Any] = response.json()

    return parse_polyline_from_json(json_data), json_data


def create_heightmap(
    polyline: np.ndarray, width: int = 1024, height: int = 1024
) -> np.ndarray:
    """
    Convert polyline to heightmap.

    Args:
        polyline: Nx2 array of (x,y) coordinates
        width: Width of output heightmap
        height: Height of output heightmap

    Returns:
        np.ndarray: 2D array representing the heightmap
    """
    # Find bounds of polyline
    x_min, y_min = np.min(polyline, axis=0)
    x_max, y_max = np.max(polyline, axis=0)

    # Create grid for heightmap
    x_coords: np.ndarray = np.linspace(x_min, x_max, width)
    y_coords: np.ndarray = np.linspace(y_min, y_max, height)
    grid_x, _ = np.meshgrid(x_coords, y_coords)

    # Interpolate heights from polyline
    # This assumes polyline is ordered by x-coordinate (terrain profile)
    # Sort by x-coordinate to ensure proper interpolation
    sorted_indices: np.ndarray = np.argsort(polyline[:, 0])
    sorted_polyline: np.ndarray = polyline[sorted_indices]

    # Create interpolation function
    f = interpolate.interp1d(
        sorted_polyline[:, 0],
        sorted_polyline[:, 1],
        kind="linear",
        bounds_error=False,
        fill_value=(sorted_polyline[0, 1], sorted_polyline[-1, 1]),
    )

    # Generate heightmap
    heightmap: np.ndarray = f(grid_x)

    # Normalize to 0-1 range
    h_min: float = np.min(heightmap)
    h_max: float = np.max(heightmap)
    if h_max > h_min:
        heightmap = (heightmap - h_min) / (h_max - h_min)

    return heightmap


def save_exr(heightmap: np.ndarray, output_path: str, metadata: dict = None) -> None:
    """
    Save heightmap as EXR file using OpenEXR with optional metadata

    Args:
        heightmap: 2D numpy array with heightmap data
        output_path: Path where to save the EXR file
        metadata: Optional dictionary of metadata to include in the EXR file
    """
    # Convert to float32
    heightmap_float32 = heightmap.astype(np.float32)

    channels = {"R": heightmap_float32}
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    # Add metadata if provided
    if metadata:
        for key, value in metadata.items():
            # String, float, and int attributes are set directly
            header[key] = value

    with OpenEXR.File(header, channels) as outfile:
        outfile.write(output_path)


def calculate_optimal_dimensions(
    polyline: np.ndarray, pixels_per_meter: float = 1.0, height: int = 1024
) -> tuple[int, int]:
    """
    Calculate optimal width based on terrain extent, with fixed or specified height.

    Args:
        polyline: Nx2 array of (x,y) coordinates
        pixels_per_meter: Optional resolution in pixels per meter
        height: Image height to use for the heightmap

    Returns:
        tuple[int, int]: Width and height in pixels
    """
    # Find bounds of polyline
    x_min, x_max = np.min(polyline[:, 0]), np.max(polyline[:, 0])

    # Calculate terrain width in meters
    terrain_width = x_max - x_min

    # Calculate width based on pixels per meter or use target width
    width = int(terrain_width * pixels_per_meter)

    return width, height


def main() -> None:
    """
    Main function to parse arguments and process the heightmap
    """
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Convert polyline data to a heightmap EXR file"
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-i", "--input", help="Input JSON file containing polyline data"
    )
    input_group.add_argument(
        "-id", "--identifier", type=int, help="ID to use with URL template"
    )

    # NOTE: if this parameter is omitted, we'll default to a name created from the JSON data
    default_output_name = "heightmap.exr"
    parser.add_argument(
        "-o", "--output", default=default_output_name, help="Output EXR file path"
    )

    parser.add_argument(
        "-p", "--ppm", type=float, default=1.0, help="Pixels per meter (default: 1.0)"
    )

    parser.add_argument(
        "-t",
        "--height",
        type=int,
        default=1024,
        help="Height of output heightmap (default: 1024)",
    )

    args = parser.parse_args()

    # Get polyline data either from file or URL
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' not found.")
            return

        print(f"Reading polyline from '{args.input}'...")
        polyline, json_data = read_polyline(args.input)
    elif args.identifier is not None:
        try:
            polyline, json_data = fetch_polyline_from_url(args.identifier)
        except Exception as e:
            print(f"Error fetching data: {e}")
            return
    else:
        parser.print_help()
        return

    # if the output file name is the default, change it to the name in the json data, but clean the name
    if args.output == default_output_name:
        raw_name = json_data.get("name", "heightmap").lower()
        # Replace spaces with underscores, then remove all non-alphanumeric/underscore
        level_name = re.sub(r"[^a-z0-9_]", "", re.sub(r"\s+", "_", raw_name))
        args.output = f"{level_name}.exr"
        print(
            f"Output file name set to '{args.output}' based on level name '{level_name}'"
        )

    # Ensure output directory exists and update output paths
    out_dir = os.path.join(os.getcwd(), "out")
    os.makedirs(out_dir, exist_ok=True)
    output_exr_path = os.path.join(out_dir, args.output)
    output_json_path = os.path.splitext(output_exr_path)[0] + ".json"

    print(f"Found {len(polyline)} points in polyline")

    # Print out the delta x and y values
    delta_x = np.max(polyline[:, 0]) - np.min(polyline[:, 0])
    delta_y = np.max(polyline[:, 1]) - np.min(polyline[:, 1])
    print(f"Delta X: {delta_x}, Delta Y: {delta_y}")

    # In main function where dimensions are processed
    print("Calculating optimal dimensions based on terrain aspect ratio...")
    args.width, args.height = calculate_optimal_dimensions(
        polyline, pixels_per_meter=args.ppm, height=args.height
    )
    print(f"Using calculated dimensions: {args.width}x{args.height}")

    print(f"Creating heightmap ({args.width}x{args.height})...")
    heightmap: np.ndarray = create_heightmap(
        polyline, width=args.width, height=args.height
    )

    # Create metadata dictionary with terrain dimensions
    metadata = {  # openEXR attributes are camelCase, prefix with ddg to namespace them (DeadDropGames)
        "ddgTerrainWidth": abs(float(delta_x)),
        "ddgTerrainHeight": abs(float(delta_y)),
        "ddgPixelsPerMeter": args.ppm,
    }

    # save the metadata to a json file in the out directory
    with open(output_json_path, "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"Saving heightmap to '{output_exr_path}'...")
    save_exr(heightmap, output_exr_path, metadata)

    print(f"Done! Heightmap saved to '{output_exr_path}'")


if __name__ == "__main__":
    main()
