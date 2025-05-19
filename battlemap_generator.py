import subprocess
import os
import json
import random
import sys
import shutil
import time

# --- Configuration ---
# INFINIGEN_PATH = "/Users/weihantu/PycharmProjects/conda_base/cse252D_dnd/infinigen" # Path to your Infinigen installation
INFINIGEN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "infinigen"))
OUTPUT_DIR_BASE = "generated_battlemaps" # Ensure this is a relative path as before
DEFAULT_ASSET_LIBRARY = "dnd_assets" # Directory for D&D specific assets

# --- Helper Functions ---

def parse_prompt(prompt: str) -> dict:
    """
    Placeholder: Parses the user's prompt to extract scene elements, style, etc.
    For "a forest with a cave" and D&D style, this might return:
    {
        "primary_biome": "forest",
        "secondary_features": ["cave"],
        "style": "dnd_fantasy",
        "mood": "mysterious" // example
    }
    This would eventually involve an LLM.
    """
    print(f"Parsing prompt: {prompt}")
    # Simple keyword matching for now
    parsed = {"primary_biome": "generic", "secondary_features": [], "style": "dnd_fantasy"}
    if "forest" in prompt.lower():
        parsed["primary_biome"] = "forest"
    if "cave" in prompt.lower():
        parsed["secondary_features"].append("cave")
    if "mountain" in prompt.lower():
        parsed["primary_biome"] = "mountain" # Example, might override forest
    # ... more rules
    return parsed

def select_infinigen_config(parsed_prompt: dict, scene_scale_factor: float = 1.0) -> tuple[str, list[str], list[str]]:
    """
    Selects or generates Infinigen .gin configuration files and parameters
    based on the parsed prompt.

    Returns:
        (generator_module, base_gin_files, override_params)
        generator_module: e.g., 'infinigen_examples.generate_terrain', 'infinigen_examples.generate_indoors'
        base_gin_files: list of .gin files to use
        override_params: list of '-p' overrides for Infinigen
    """
    print(f"Selecting Infinigen config for: {parsed_prompt}")
    generator_module = "infinigen_examples.generate_nature" # Default to nature generation
    base_gin_files = ["forest_template.gin"] # Default to forest template
    
    # Extract any specific parameters from the parsed prompt if available
    # For now, using fixed defaults that match our simplified .gin for consistency
    params = parsed_prompt.get("generation_params", {}) 

    override_params = [
        f"compose_nature.trees_chance={params.get('trees_chance', 0.4)}",
        f"compose_nature.bushes_chance={params.get('bushes_chance', 0.3)}",
        f"compose_nature.ground_leaves_chance={params.get('ground_leaves_chance', 0.4)}",
        f"compose_nature.grass_chance={params.get('grass_chance', 0.3)}",
        f"compose_nature.ferns_chance={params.get('ferns_chance', 0.1)}",
        f"compose_nature.flowers_chance={params.get('flowers_chance', 0.05)}",
        f"compose_nature.rocks_chance={params.get('rocks_chance', 0.02)}",
        f"compose_nature.boulders_chance={params.get('boulders_chance', 0.02)}",
        f"compose_nature.monocots_chance={params.get('monocots_chance', 0.01)}",
        
        "compose_nature.terrain_enabled=True",
        "compose_nature.coarse_terrain_enabled=True",
        "compose_nature.terrain_surface_enabled=True",
        
        # Minimize atmosphere for speed (already present)
        f"compose_nature.atmosphere_chance={params.get('atmosphere_chance', 0.0)}",
        f"compose_nature.volumetric_clouds_chance={params.get('volumetric_clouds_chance', 0.0)}",
        f"compose_nature.wind_chance={params.get('wind_chance', 0.0)}",
        f"compose_nature.turbulence_chance={params.get('turbulence_chance', 0.0)}",
        f"compose_nature.rain_particles_chance={params.get('rain_particles_chance', 0.0)}",
        f"compose_nature.leaf_particles_chance={params.get('leaf_particles_chance', 0.0)}",

        # Ensure caves are off for simple forest
        "scene.caves_chance=0.0",
        "Caves.n_lattice=0", # Attempt to disable cave structure via __init__ param

        # Minimize erosion and disable snowfall (NEW)
        "run_erosion.n_iters=[0,0]",
        "ant_landscape_asset.snowfall=0",
        "multi_mountains_asset.snowfall=0",
        "coast_asset.snowfall=0",
        "get_land_process.snowfall_enabled=0",
        "populate_scene.snow_layer_chance=0", # From base_nature, but good to ensure

        # Attempt to disable MultiMountains by clearing LandTiles -> THIS CAUSED KeyError
        # "LandTiles.tiles=[]" # Reverted

        # Parameters to make MultiMountains generate flat/empty - REPLACED by scaled values
        # "multi_mountains_params.height=0",
        # "multi_mountains_params.coverage=0",
        # "multi_mountains_params.slope_height=0", # Keep slope height small or zero if not prominent mountains desired

        # Scaled parameters for MultiMountains
        f"multi_mountains_params.height={50.0 * scene_scale_factor}",       # Base height 50, scaled
        f"multi_mountains_params.coverage={0.2 * scene_scale_factor}",     # Base coverage 0.2, scaled
        f"multi_mountains_params.slope_height={10.0 * scene_scale_factor}", # Base slope height 10, scaled

        "multi_mountains_asset.erosion=False", # Already globally off, but good to be sure for this asset
        "multi_mountains_asset.snowfall=False", # Already globally off, but good to be sure for this asset

        # Parameters to make the overall scene extent smaller (battlemap like)
        # Values from infinigen_examples/configs_nature/forest_template.gin (for "smallest possible scene")
        # Further reduced to make the map even smaller (approx 1/4 area)
        "compose_nature.inview_distance=5", # Halved from 10
        "placement.populate_all.dist_cull=5", # Halved from 10
        "compose_nature.near_distance=1", # Halved from 2
        "compose_nature.center_distance=2"  # Halved from 5 (rounded down)
    ]

    if parsed_prompt.get("primary_biome") == "forest":
        if "cave" in parsed_prompt.get("secondary_features", []):
            print("Forest with cave requested. Overriding scene.caves_chance to 1.0 and simplifying cave params.")
            override_params = [p for p in override_params if not p.startswith("scene.caves_chance")]
            override_params = [p for p in override_params if not p.startswith("Caves.on_the_fly_instances")] # Ensure this is also removed if we re-enable caves
            override_params.append("scene.caves_chance=1.0")
            # For actual cave generation, we would let on_the_fly_instances be its default or set it > 0
            # override_params.append("Caves.on_the_fly_instances=1") # e.g., for one cave
            # Add parameters to simplify cave generation for speed
            override_params.append("Caves.n_lattice=1")
            override_params.append("Caves.frequency=0.1") # Higher frequency might lead to smaller/quicker caves
            override_params.append("Caves.randomness=0.0") # Less randomness for potential speedup
            # override_params.append("Caves.is_horizontal=1") # Default in cave.gin
            # override_params.append("Caves.scale_increase=1") # Default in cave.gin
        else:
            print("Forest requested - using forest_template.gin (defaulting to no caves).")
    elif parsed_prompt.get("primary_biome") == "desert":
        base_gin_files = ["desert_template.gin"] # Assuming this exists or will be created
        # Example: override_params.append(" সাহারা.desert_specific_param=value")
        print("Desert biome selected.")
    # Add more biome/feature logic here

    return generator_module, base_gin_files, override_params

def run_infinigen_generation(scene_name: str, generator_module: str, gin_files: list[str], override_params: list[str], seed: int) -> str:
    """
    Runs the main Infinigen generation process, now in two stages: coarse and populate.
    Returns the absolute path to the output scene folder.
    """
    output_scene_folder_relative = os.path.join(OUTPUT_DIR_BASE, scene_name, "infinigen_raw")
    os.makedirs(output_scene_folder_relative, exist_ok=True)
    output_scene_folder_absolute = os.path.abspath(output_scene_folder_relative)

    # --- Stage 1: Coarse Terrain Generation ---
    print("--- Running Infinigen Generation: STAGE 1 (coarse) ---")
    coarse_cmd = [
        sys.executable, "-m", generator_module,
        "--output_folder", output_scene_folder_absolute, # Use absolute path
        "--seed", str(seed),
        "--task", "coarse",
    ]
    for gin_file in gin_files:
        coarse_cmd.extend(["-g", gin_file])
    for param in override_params:
        coarse_cmd.extend(["-p", param])

    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{INFINIGEN_PATH}:{os.path.join(INFINIGEN_PATH, 'src')}:{python_path}"

    print(f"Running Infinigen (coarse): {' '.join(coarse_cmd)}")
    try:
        process_coarse = subprocess.run(coarse_cmd, cwd=INFINIGEN_PATH, capture_output=True, text=True, check=True, env=env, timeout=600) # 10 min timeout
        print("Infinigen coarse generation successful.")
        if process_coarse.stdout: print(f"Coarse STDOUT:\n{process_coarse.stdout}")
        if process_coarse.stderr: print(f"Coarse STDERR:\n{process_coarse.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"Error during Infinigen coarse generation: {e}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"Infinigen coarse generation timed out.")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise

    # --- Stage 2: Populate Scene ---
    print("--- Running Infinigen Generation: STAGE 2 (populate) ---")
    populate_cmd = [
        sys.executable, "-m", generator_module,
        "--input_folder", output_scene_folder_absolute, # Use absolute path
        "--output_folder", output_scene_folder_absolute, # Use absolute path
        "--seed", str(seed), # Seed might be needed again for consistency
        "--task", "populate",
    ]
    for gin_file in gin_files: # Gin files might be needed again for population parameters
        populate_cmd.extend(["-g", gin_file])
    for param in override_params: # Overrides are also needed for population
        populate_cmd.extend(["-p", param])

    print(f"Running Infinigen (populate): {' '.join(populate_cmd)}")
    try:
        process_populate = subprocess.run(populate_cmd, cwd=INFINIGEN_PATH, capture_output=True, text=True, check=True, env=env, timeout=600) # Another 10 min for populate
        print("Infinigen populate generation successful.")
        if process_populate.stdout: print(f"Populate STDOUT:\n{process_populate.stdout}")
        if process_populate.stderr: print(f"Populate STDERR:\n{process_populate.stderr}")
        return output_scene_folder_absolute # Return absolute path
    except subprocess.CalledProcessError as e:
        print(f"Error during Infinigen populate generation: {e}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"Infinigen populate generation timed out.")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise

def run_infinigen_export(scene_name: str, infinigen_raw_folder_absolute: str) -> str:
    """
    Exports the generated scene to a usable format (e.g., USD for Blender/Three.js).
    infinigen_raw_folder_absolute: Absolute path to the raw Infinigen output.
    Returns the absolute path to the main exported file or the export folder on failure.
    """
    # Define the true output location based on exporter's apparent behavior (relative to INFINIGEN_PATH CWD)
    true_export_output_dir = os.path.join(INFINIGEN_PATH, OUTPUT_DIR_BASE, scene_name, "exported_scene")
    os.makedirs(true_export_output_dir, exist_ok=True)

    export_module = "infinigen.tools.export" # Standard export tool

    cmd = [
        sys.executable, "-m", export_module,
        "--input_folder", infinigen_raw_folder_absolute, # Use absolute path from generation stage
        "--output_folder", true_export_output_dir,      # Tell exporter to output here
        "-f", "usdc", # USD Crate format, good for Blender/Omniverse
        # "-f", "glb", # Alternative: glTF Binary for Three.js, might need different export flags
        "-r", "512", # Resolution for baked textures, changed from 1024 to 512
        "--omniverse" # For Isaac Sim / Omniverse compatibility, might imply USD
        # Add more export options as needed (e.g., simplifying geometry, specific asset types)
    ]
    print(f"Running Infinigen export: {' '.join(cmd)}")
    try:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{INFINIGEN_PATH}:{os.path.join(INFINIGEN_PATH, 'src')}:{python_path}"

        # CWD for export process is INFINIGEN_PATH
        process = subprocess.run(cmd, cwd=INFINIGEN_PATH, capture_output=True, text=True, check=True, env=env, timeout=600) # 10 min timeout
        print("Infinigen export successful.")
        print(process.stdout)

        # --- DEBUG: Check directory contents immediately after export ---
        debug_ls_cmd = ["ls", "-la", true_export_output_dir] # Check the true output location
        print(f"DEBUG: Running: {' '.join(debug_ls_cmd)}")
        debug_process = subprocess.run(debug_ls_cmd, capture_output=True, text=True)
        print(f"DEBUG: ls output for {true_export_output_dir}:\nSTDOUT:\n{debug_process.stdout}\nSTDERR:\n{debug_process.stderr}")
        # --- END DEBUG ---
        
        # The export tool sometimes places it inside a folder named like <scene_name>.blend or just export_scene.blend
        # e.g., INFINIGEN_PATH/generated_battlemaps/scene_name/exported_scene/export_scene.blend/export_scene.usdc

        # --- Attempt 1: Known nested path based on exporter behavior ---
        known_nested_blend_dir_name = "export_scene.blend"
        attempted_known_nested_path = os.path.join(true_export_output_dir, known_nested_blend_dir_name, "export_scene.usdc")
        print(f"Attempt 1: Checking known nested path: {attempted_known_nested_path}")
        if os.path.exists(attempted_known_nested_path):
            print(f"Found USD via known nested path: {attempted_known_nested_path}")
            return attempted_known_nested_path

        # --- Attempt 2: Check common direct paths (less likely with current exporter but good fallback) ---
        direct_usd_path = os.path.join(true_export_output_dir, "scene.usdc")
        print(f"Attempt 2: Checking direct path scene.usdc: {direct_usd_path}")
        if os.path.exists(direct_usd_path):
            print(f"Found exported USD file directly: {direct_usd_path}")
            return direct_usd_path
            
        direct_export_scene_usd_path = os.path.join(true_export_output_dir, "export_scene.usdc")
        print(f"Attempt 3: Checking direct path export_scene.usdc: {direct_export_scene_usd_path}")
        if os.path.exists(direct_export_scene_usd_path):
            print(f"Found exported USD file directly (export_scene.usdc): {direct_export_scene_usd_path}")
            return direct_export_scene_usd_path

        # --- Attempt 4: Fallback to os.listdir and searching (original more robust loop) ---
        print(f"Attempt 4: Falling back to os.listdir on {true_export_output_dir}")
        try:
            print(f"Listing contents of export folder: {true_export_output_dir}")
            dir_contents = os.listdir(true_export_output_dir)
            print(f"Contents: {dir_contents}")
            for item in dir_contents:
                item_path = os.path.join(true_export_output_dir, item)
                print(f"Checking item: {item_path}, is_dir: {os.path.isdir(item_path)}, ends_with_blend: {item.endswith('.blend')}")
                if os.path.isdir(item_path) and item.endswith(".blend"):
                    print(f"Found .blend directory: {item_path}")
                    nested_usd_path = os.path.join(item_path, "export_scene.usdc")
                    print(f"Checking for nested USD: {nested_usd_path}, exists: {os.path.exists(nested_usd_path)}")
                    if os.path.exists(nested_usd_path):
                        print(f"Found nested USD file: {nested_usd_path}")
                        return nested_usd_path
                    
                    nested_scene_usd_path = os.path.join(item_path, "scene.usdc")
                    print(f"Checking for nested scene.usdc: {nested_scene_usd_path}, exists: {os.path.exists(nested_scene_usd_path)}")
                    if os.path.exists(nested_scene_usd_path):
                        print(f"Found nested USD file (scene.usdc): {nested_scene_usd_path}")
                        return nested_scene_usd_path
        except FileNotFoundError:
            print(f"Warning: Output export folder {true_export_output_dir} not found during USD search.")

        # Fallback to broader search if specific nested structures aren't found
        print(f"Specific USD paths not found, starting broader search in {true_export_output_dir}...")
        for root, _, files in os.walk(true_export_output_dir):
            for file in files:
                if file.endswith((".usd", ".usda", ".usdc")):
                    found_file_path = os.path.join(root, file)
                    print(f"Found USD file via walk: {found_file_path}")
                    return found_file_path
        
        print(f"Warning: Could not find main exported USD file in {true_export_output_dir} after all checks.")
        return true_export_output_dir # Return folder (absolute path) if specific file not found

    except subprocess.CalledProcessError as e:
        print(f"Error during Infinigen export: {e}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"Infinigen export timed out.")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise


def post_process_scene(exported_scene_path: str, parsed_prompt: dict):
    """
    Placeholder: Post-process the scene.
    This could involve:
    - Using Blender scripting to further refine the scene.
    - Adding/placing D&D specific assets generated by TRELLIS.
    - Adjusting lighting, materials for D&D style if not fully handled by Infinigen.
    - Optimizing geometry for real-time performance.
    """
    print(f"Post-processing scene (placeholder): {exported_scene_path} with prompt context: {parsed_prompt}")
    # Scaling is now handled by generation parameters directly.
    # If other post-processing is needed, it can be added here.
    print("Post-processing step (currently a placeholder).")
    return exported_scene_path # Return the original path as no modification is done here


# --- Main Function ---
def generate_battlemap(prompt: str, scene_name: str = None, scene_scale_factor: float = 0.1):
    """
    Generates a D&D battlemap based on a text prompt.
    """
    start_time = time.time() # Record start time

    if not scene_name:
        # Generate a unique scene name if not provided
        scene_name = prompt.lower().replace(" ", "_").replace("'", "") + f"_{random.randint(1000, 9999)}"

    print(f"Starting battlemap generation for: '{prompt}' (Scene: {scene_name})")

    # 1. Parse Prompt (Eventually LLM-driven)
    parsed_elements = parse_prompt(prompt)
    print(f"Parsed elements: {parsed_elements}")

    # 2. Select/Generate Infinigen Configuration
    # This is a critical step and will need significant development.
    # It needs to map semantic concepts from the prompt to Infinigen's procedural rules.
    # For "a forest with a cave" in D&D style:
    # - Choose terrain type: forest
    # - Add features: cave (might be a special asset or terrain modification)
    # - Apply D&D style: specific textures, lighting, asset choices, atmosphere.
    try:
        generator_module, gin_files, override_params = select_infinigen_config(parsed_elements, scene_scale_factor=scene_scale_factor)
        seed = random.randint(0, 100000)

        # Create necessary output directories
        os.makedirs(os.path.join(OUTPUT_DIR_BASE, scene_name), exist_ok=True)
        # Create dummy gin files if they don't exist, for the script to run initially
        # These should be proper Infinigen config files.
        project_configs_dir = "infinigen_configs"
        os.makedirs(project_configs_dir, exist_ok=True)

        for gin_file in gin_files:
            local_gin_path = os.path.join(project_configs_dir, gin_file)
            if not os.path.exists(local_gin_path):
                print(f"Creating dummy GIN file: {local_gin_path} (NEEDS REAL CONFIG)")
                with open(local_gin_path, "w") as f:
                    f.write("# Minimal dummy GIN config for " + gin_file + "\n")
            
            # Also copy this to a potential Infinigen search path
            infinigen_search_dir = os.path.join(INFINIGEN_PATH, "infinigen_examples", "configs_nature")
            os.makedirs(infinigen_search_dir, exist_ok=True)
            target_infinigen_gin_path = os.path.join(infinigen_search_dir, gin_file)
            print(f"Copying {local_gin_path} to {target_infinigen_gin_path}")
            shutil.copy(local_gin_path, target_infinigen_gin_path)


        # 3. Run Infinigen Generation
        # This involves calling Infinigen's command-line tools or Python API
        # with the selected configurations.
        # Example: `python -m infinigen.run --config my_dnd_forest_config.gin --output_folder ...`
        print("Step 3: Running Infinigen generation...")
        raw_scene_folder = run_infinigen_generation(scene_name, generator_module, gin_files, override_params, seed)
        print(f"Raw Infinigen output at: {raw_scene_folder}")

        # 4. Run Infinigen Export (to USD or glTF)
        print("Step 4: Running Infinigen export...")
        exported_scene_file = run_infinigen_export(scene_name, raw_scene_folder)
        print(f"Exported scene at: {exported_scene_file}")

        # 5. Post-processing (Optional, e.g., in Blender)
        # - Add specific D&D assets (from TRELLIS, or a pre-made library)
        # - Fine-tune lighting, camera for a "battlemap" view
        # - Optimize for performance
        print("Step 5: Post-processing...")
        final_scene_file = post_process_scene(exported_scene_file, parsed_elements)

        print(f"Battlemap '{scene_name}' generation complete. Main file: {final_scene_file}")
        return final_scene_file

    except subprocess.CalledProcessError as e:
        print(f"A subprocess command failed: {e.cmd}")
        print(f"Return code: {e.returncode}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        print(f"Battlemap generation for '{scene_name}' FAILED.")
        return None
    except subprocess.TimeoutExpired as e:
        print(f"A subprocess command timed out: {e.cmd}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        print(f"Battlemap generation for '{scene_name}' FAILED due to timeout.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during battlemap generation for '{scene_name}': {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        end_time = time.time() # Record end time
        duration = end_time - start_time
        print(f"Total generation time for '{scene_name}': {duration:.2f} seconds.")

if __name__ == "__main__":
    # --- Configuration at the start of the script ---
    # Ensure INFINIGEN_PATH is correctly set by the user or environment
    if not os.path.isdir(INFINIGEN_PATH):
        print(f"Error: INFINIGEN_PATH '{INFINIGEN_PATH}' is not a valid directory.")
        print("Please set the INFINIGEN_PATH variable in the script to your Infinigen installation directory.")
        exit(1)

    # Create base output directory
    os.makedirs(OUTPUT_DIR_BASE, exist_ok=True)

    # Example Prompts:
    # prompt1 = "A dark, ancient forest with a hidden, mossy cave entrance, D&D fantasy style"
    # battlemap_file1 = generate_battlemap(prompt1)
    # if battlemap_file1:
    #     print(f"Generated: {battlemap_file1}")

    prompt2 = "A rugged mountain pass with a narrow chasm and a small, crumbling watchtower, D&D style"
    # For testing, let's simplify to just the biome first to ensure Infinigen runs
    # prompt2_simple_biome = "mountain terrain"
    # battlemap_file2 = generate_battlemap(prompt2_simple_biome, scene_name="mountain_test")


    # More focused test for "forest with a cave"
    # prompt_forest_cave = "a forest with a cave"
    # battlemap_fc = generate_battlemap(prompt_forest_cave, scene_name="forest_cave_test")
    # if battlemap_fc:
    #     print(f"Generated forest_cave_test: {battlemap_fc}")
    # else:
    #     print(f"Failed to generate forest_cave_test.")

    # Test for forest only
    prompt_forest_only = "a simple forest"
    print(f"--- Running test for: {prompt_forest_only} ---")
    battlemap_fo = generate_battlemap(prompt_forest_only, scene_name="forest_only_test")
    if battlemap_fo:
        print(f"Generated forest_only_test: {battlemap_fo}")
    else:
        print(f"Failed to generate forest_only_test.")

    # You would then take the exported_scene_file (e.g., a .usd or .glb file)
    # and load it into Blender or your Three.js application.