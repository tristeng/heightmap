# Heightmap Generator

A Python tool for converting 2D polyline data into heightmap EXR files. The tool can read polyline data from local JSON files or fetch it from a remote API, then interpolate the data to create elevation maps.

This repo was written 95% by AI while I was watching TV using Claude 3.7 Sonnet Thinking Copilot model. I created this so I could convert some 2D levels I had created for a mobile game called [StuntSki](https://deaddropgames.com/stuntski/) into heightmaps I could import into Godot. The levels are available through an API on the above website.

## Installation

This project requires Python 3.13+ and depends on libraries like numpy, scipy, imageio, and requests.

```bash
# Clone the repository
git clone <repository-url>
cd heightmap

# Install dependencies with UV: https://docs.astral.sh/uv/
uv venv --python 3.13.3
uv sync
```

## Usage

The heightmap generator accepts input from either a local JSON file or a remote API endpoint:

```bash
# Generate heightmap from local JSON file
python heightmap_generator.py -i input.json -o output.exr

# Generate heightmap from remote API using an ID
python heightmap_generator.py -id 2 -o output.exr

# Specify custom dimensions (p is pixels per metre)
python heightmap_generator.py -i input.json -p 2 -t 128 -o output.exr
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `-i`, `--input` | Input JSON file containing polyline data |
| `-id`, `--identifier` | ID to use with the API URL template |
| `-o`, `--output` | Output EXR file path (default: heightmap.exr) |
| `-p`, `--ppm` | Pixels per metre (default: 1.0) |
| `-t`, `--height` | Height of output heightmap (default: 1024) |

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

## Importing into Godot
You can use the heightmap by creating a `StaticBody3D` with a `CollisionShape3D` as a child. Specify a `HeightMapShape3D` as the Shape for the collision shape, and then you can use some GDScript code like so:
```python
extends CollisionShape3D


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
    var heightmap_texture: = ResourceLoader.load("res://output.exr")
    var heightmap_image = heightmap_texture.get_image()

    # The minimum height should be the lowest point of your height map in metres
    var height_min = -100.0  # My height maps start at 0,0 and descend since they are ski run
    var height_max = 0.0

    # The height map will be centred by default - you may want to adjust its position and rotation here

    self.shape.update_map_data_from_image(heightmap_image, height_min, height_max)
```