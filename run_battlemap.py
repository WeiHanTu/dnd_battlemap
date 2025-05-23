from battlemap_generator import generate_battlemap

# Generate a simple forest battlemap
prompt = "a forest with a small clearing"
scene_name = "test_forest_map"
scene_scale_factor = 0.1  # Smaller scale for faster generation

# Run the generator
generate_battlemap(
    prompt=prompt,
    scene_name=scene_name,
    scene_scale_factor=scene_scale_factor
)