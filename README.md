# Heightmap Generator

A Python tool for converting 2D polyline data into heightmap EXR files. The tool can read polyline data from local JSON files or fetch it from a remote API, then interpolate the data to create elevation maps.

## Installation

This project requires Python 3.13+ and depends on libraries like numpy, scipy, imageio, and requests.

```bash
# Clone the repository
git clone <repository-url>
cd heightmap

# Install dependencies with UV: https://docs.astral.sh/uv/
uv venv
uv sync
```

## Usage

The heightmap generator accepts input from either a local JSON file or a remote API endpoint:

```bash
# Generate heightmap from local JSON file
python heightmap_generator.py -i input.json -o output.exr

# Generate heightmap from remote API using an ID
python heightmap_generator.py -id 12345 -o output.exr

# Automatically calculate optimal dimensions based on terrain shape
python heightmap_generator.py -i input.json -a -o output.exr

# Specify custom dimensions
python heightmap_generator.py -i input.json -w 2048 -t 1024 -o output.exr
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-i`, `--input` | Input JSON file containing polyline data |
| `-id`, `--identifier` | ID to use with the API URL template |
| `-o`, `--output` | Output EXR file path (default: heightmap.exr) |
| `-w`, `--width` | Width of output heightmap (default: 1024) |
| `-t`, `--height` | Height of output heightmap (default: 1024) |
| `-a`, `--auto-dimensions` | Automatically calculate dimensions based on terrain aspect ratio |

## Input Format

The JSON input is expected to have the following structure:

```json
{
  "polyLines": [
    {
      "points": [
        {"x": 0.0, "y": 0.0},
        {"x": 1.0, "y": 0.5},
        {"x": 2.0, "y": 0.3}
      ]
    }
  ]
}
```

## How It Works

1. The tool extracts (x,y) coordinates from the polyline data
2. It finds the bounding box of the terrain and creates a coordinate grid
3. The polyline is sorted by x-coordinate and used for linear interpolation
4. The resulting heightmap is normalized to a 0-1 range
5. The heightmap is saved as an EXR file with float32 precision

## Remote API

The tool can fetch polyline data from a remote API using the URL template:
`https://deaddropgames.com/stuntski/api/levels/{id}`

## Tips and Notes
### Match the Aspect Ratio
The heightmap's dimensions should match the aspect ratio of your terrain to avoid distortion:
```python
# Example: terrain is 2000m long and 100m wide (20:1 ratio)
python heightmap_generator.py -i terrain.json -w 2048 -t 128
```
### Resolution Distribution
Allocate pixels efficiently:
* More resolution along the length (skiing direction)
* Less resolution across the width

### Memory Considerations
If your terrain is extremely long (like 10:1 ratio or more):
* Consider limiting total pixel count (e.g., 4-8 million pixels maximum)
* Example: 4096x512 instead of 8192x1024