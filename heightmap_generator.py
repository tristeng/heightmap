import argparse
import json
import os
import requests
from typing import Any
import numpy as np
import OpenEXR
from scipy import interpolate
import array
import Imath

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
    points: list[tuple[float, float]] = [(point.get("x", 0.0), point.get("y", 0.0)) for point in points_data]
    
    return np.array(points)

def read_polyline(file_path: str) -> np.ndarray:
    """
    Read polyline data from JSON file.
    
    The JSON is expected to have a "polyLines" array where the first element
    has a "points" array containing objects with "x" and "y" attributes.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        np.ndarray: Array of (x,y) coordinates
    """
    with open(file_path, "r") as f:
        json_data: dict[str, Any] = json.load(f)
    
    return parse_polyline_from_json(json_data)

def fetch_polyline_from_url(id: int) -> np.ndarray:
    """
    Fetch polyline data from a URL using an ID parameter.
    
    Args:
        id: ID to insert into the URL template
        
    Returns:
        np.ndarray: Array of (x,y) coordinates
    """
    url = URL_TEMPLATE.format(id=id)
    print(f"Fetching data from {url}...")
    
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception if request failed
    
    json_data: dict[str, Any] = response.json()
    
    return parse_polyline_from_json(json_data)

def create_heightmap(polyline: np.ndarray, width: int = 1024, height: int = 1024) -> np.ndarray:
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
        fill_value=(sorted_polyline[0, 1], sorted_polyline[-1, 1])
    )
    
    # Generate heightmap
    heightmap: np.ndarray = f(grid_x)
    
    # Normalize to 0-1 range
    h_min: float = np.min(heightmap)
    h_max: float = np.max(heightmap)
    if h_max > h_min:
        heightmap = (heightmap - h_min) / (h_max - h_min)
    
    return heightmap

def save_exr(heightmap: np.ndarray, output_path: str) -> None:
    """
    Save heightmap as EXR file using OpenEXR (grayscale, single channel)
    
    Args:
        heightmap: 2D numpy array with heightmap data
        output_path: Path where to save the EXR file
    """
    # Get dimensions
    height, width = heightmap.shape
    
    # Convert to float32 and make sure data is in proper format
    heightmap_float32 = heightmap.astype(np.float32)
    
    # Create header with just R channel - single channel EXR and Godot wants it on the R channel
    header = OpenEXR.Header(width, height)
    half_chan = Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))
    header["channels"] = dict([("R", half_chan)])
    
    # Create OpenEXR output file
    exr = OpenEXR.OutputFile(output_path, header)
    
    # Convert data to bytes
    R = array.array("f", heightmap_float32.flatten()).tobytes()
    
    # Write to file (single channel only)
    exr.writePixels({"R": R})
    
    # Close the file
    exr.close()

def calculate_optimal_dimensions(polyline: np.ndarray, 
                                 pixels_per_meter: float = 1.0, 
                                 height: int = 1024) -> tuple[int, int]:
    """
    Calculate optimal width based on terrain extent, with fixed or specified height.
    
    Args:
        polyline: Nx2 array of (x,y) coordinates
        height: Height to use for the heightmap
        pixels_per_meter: Optional resolution in pixels per meter
        
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
    parser = argparse.ArgumentParser(description="Convert polyline data to a heightmap EXR file")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input", 
                          help="Input JSON file containing polyline data")
    input_group.add_argument("-id", "--identifier", 
                          type=int,
                          help="ID to use with URL template")
    
    parser.add_argument("-o", "--output", 
                      default="heightmap.exr",
                      help="Output EXR file path")
    
    parser.add_argument("-p", "--ppm", 
                      type=float, 
                      default=1.0, 
                      help="Pixels per meter (default: 1.0)")
    
    parser.add_argument("-t", "--height", 
                      type=int, 
                      default=1024, 
                      help="Height of output heightmap (default: 1024)")

    args = parser.parse_args()
    
    # Get polyline data either from file or URL
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' not found.")
            return
            
        print(f"Reading polyline from '{args.input}'...")
        polyline: np.ndarray = read_polyline(args.input)
    elif args.identifier is not None:
        try:
            polyline: np.ndarray = fetch_polyline_from_url(args.identifier)
        except Exception as e:
            print(f"Error fetching data: {e}")
            return
    else:
        parser.print_help()
        return
    
    print(f"Found {len(polyline)} points in polyline")

    # Print out the delta x and y values
    delta_x = np.max(polyline[:, 0]) - np.min(polyline[:, 0])
    delta_y = np.max(polyline[:, 1]) - np.min(polyline[:, 1])
    print(f"Delta X: {delta_x}, Delta Y: {delta_y}")
    
    # In main function where dimensions are processed
    print("Calculating optimal dimensions based on terrain aspect ratio...")
    args.width, args.height = calculate_optimal_dimensions(polyline, 
                                                            pixels_per_meter=args.ppm, 
                                                            height=args.height)
    print(f"Using calculated dimensions: {args.width}x{args.height}")
    
    print(f"Creating heightmap ({args.width}x{args.height})...")
    heightmap: np.ndarray = create_heightmap(polyline, width=args.width, height=args.height)
    
    print(f"Saving heightmap to '{args.output}'...")
    save_exr(heightmap, args.output)
    
    print(f"Done! Heightmap saved to '{args.output}'")

if __name__ == "__main__":
    main()