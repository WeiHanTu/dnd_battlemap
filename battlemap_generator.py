import subprocess
import os
import json
import random
import sys
import shutil

# --- Configuration ---
# INFINIGEN_PATH = "/Users/weihantu/PycharmProjects/conda_base/cse252D_dnd/infinigen" # Path to your Infinigen installation
INFINIGEN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "infinigen"))
OUTPUT_DIR_BASE = "generated_battlemaps"
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

def select_infinigen_config(parsed_prompt: dict) -> tuple[str, list[str], list[str]]:
    """
    Selects or generates Infinigen .gin configuration files and parameters
    based on the parsed prompt.

    Returns:
        (task_type, generator_module, base_gin_files, override_params)
        task_type: e.g., 'terrain', 'indoors'
        generator_module: e.g., 'infinigen_examples.generate_terrain', 'infinigen_examples.generate_indoors'
        base_gin_files: list of .gin files to use
        override_params: list of '-p' overrides for Infinigen
    """
    print(f"Selecting Infinigen config for: {parsed_prompt}")
    generator_module = "infinigen_examples.generate_nature" # Default to nature generation
    base_gin_files = ["forest_template.gin"] # Default to forest template
    override_params = []

    if parsed_prompt["primary_biome"] == "forest":
        base_gin_files = ["forest_template.gin"]
        # Add forest-specific overrides
        override_params.extend([
            "-p", "compose_nature.trees_chance=0.8",
            "-p", "compose_nature.bushes_chance=0.6",
            "-p", "compose_nature.ground_leaves_chance=0.9",
            "-p", "compose_nature.grass_chance=0.9",
        ])
        if "cave" in parsed_prompt["secondary_features"]:
            # For caves, we'll need to adjust terrain parameters
            override_params.extend([
                "-p", "compose_nature.terrain_enabled=True",
                "-p", "compose_nature.coarse_terrain_enabled=True",
                "-p", "compose_nature.terrain_surface_enabled=True",
            ])

    elif parsed_prompt["primary_biome"] == "mountain":
        base_gin_files = ["mountain_template.gin"]
        override_params.extend([
            "-p", "compose_nature.trees_chance=0.3",
            "-p", "compose_nature.rocks_chance=1.0",
            "-p", "compose_nature.boulders_chance=0.8",
        ])
        if "cave" in parsed_prompt["secondary_features"]:
            override_params.extend([
                "-p", "compose_nature.terrain_enabled=True",
                "-p", "compose_nature.coarse_terrain_enabled=True",
            ])

    # D&D Style adjustments
    if parsed_prompt["style"] == "dnd_fantasy":
        override_params.extend([
            "-p", "compose_nature.wind_chance=0.7",
            "-p", "compose_nature.turbulence_chance=0.4",
            "-p", "compose_nature.rain_particles_chance=0.05",
            "-p", "compose_nature.leaf_particles_chance=0.1",
        ])

    return generator_module, base_gin_files, override_params

def run_infinigen_generation(scene_name: str, generator_module: str, gin_files: list[str], override_params: list[str], seed: int) -> str:
    """
    Runs the main Infinigen generation process.
    """
    output_scene_folder = os.path.join(OUTPUT_DIR_BASE, scene_name, "infinigen_raw")
    os.makedirs(output_scene_folder, exist_ok=True)

    # Check if INFINIGEN_PATH/infinigen_examples exists, if not, try INFINIGEN_PATH/src/infinigen/assets/infinigen_examples
    infinigen_script_path = os.path.join(INFINIGEN_PATH, generator_module.replace('.', os.sep) + ".py")
    if not os.path.exists(infinigen_script_path):
        # Fallback for some structures where examples are deeper
        potential_path = os.path.join(INFINIGEN_PATH, "src", "infinigen", "assets", generator_module.replace('.', os.sep) + ".py")
        if os.path.exists(potential_path):
            # This logic is a bit tricky as `python -m` expects module paths
            # For simplicity, we'll stick to the direct python call if module path fails.
            # A better way would be to ensure PYTHONPATH is set correctly to include INFINIGEN_PATH
            pass # Keep using -m for now, assuming PYTHONPATH is set or it's in a standard location.


    cmd = [
        sys.executable, "-m", generator_module,
        "--output_folder", output_scene_folder,
        "--seed", str(seed),
        "--task", "coarse", # Or 'fine_terrain', 'populate' etc. 'coarse' for speed.
    ]
    for gin_file in gin_files:
        # Pass only the filename, relying on Infinigen's search paths
        # (since we copied the file into one of its likely search paths)
        cmd.extend(["-g", gin_file])

    cmd.extend(override_params)

    # Add any D&D specific asset paths to overrides if necessary
    # e.g. -p some_asset_factory.asset_path='path/to/dnd_assets_folder'

    print(f"Running Infinigen generation: {' '.join(cmd)}")
    try:
        # Set PYTHONPATH to include the Infinigen root, so `python -m` works
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{INFINIGEN_PATH}:{os.path.join(INFINIGEN_PATH, 'src')}:{python_path}"

        process = subprocess.run(cmd, cwd=INFINIGEN_PATH, capture_output=True, text=True, check=True, env=env, timeout=600) # 10 min timeout
        print("Infinigen generation successful.")
        print(process.stdout)
        return output_scene_folder
    except subprocess.CalledProcessError as e:
        print(f"Error during Infinigen generation: {e}")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"Infinigen generation timed out after 600 seconds.")
        print(f"Stderr: {e.stderr}")
        print(f"Stdout: {e.stdout}")
        # Consider the partial output as a failure for now, or try to salvage
        raise

def run_infinigen_export(scene_name: str, infinigen_raw_folder: str) -> str:
    """
    Exports the generated scene to a usable format (e.g., USD for Blender/Three.js).
    """
    output_export_folder = os.path.join(OUTPUT_DIR_BASE, scene_name, "exported_scene")
    os.makedirs(output_export_folder, exist_ok=True)

    export_module = "infinigen.tools.export" # Standard export tool

    cmd = [
        sys.executable, "-m", export_module,
        "--input_folder", infinigen_raw_folder,
        "--output_folder", output_export_folder,
        "-f", "usdc", # USD Crate format, good for Blender/Omniverse
        # "-f", "glb", # Alternative: glTF Binary for Three.js, might need different export flags
        "-r", "1024", # Resolution for baked textures, adjust as needed
        "--omniverse" # For Isaac Sim / Omniverse compatibility, might imply USD
        # Add more export options as needed (e.g., simplifying geometry, specific asset types)
    ]
    print(f"Running Infinigen export: {' '.join(cmd)}")
    try:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{INFINIGEN_PATH}:{os.path.join(INFINIGEN_PATH, 'src')}:{python_path}"

        process = subprocess.run(cmd, cwd=INFINIGEN_PATH, capture_output=True, text=True, check=True, env=env, timeout=120) # 2 min timeout
        print("Infinigen export successful.")
        print(process.stdout)
        # The main output file is usually scene.usdc or similar in the output_export_folder
        exported_file = os.path.join(output_export_folder, "scene.usdc") # Check actual output name
        if not os.path.exists(exported_file):
             # Try to find the main USD file, sometimes it has a different name or is in a subfolder
            for root, _, files in os.walk(output_export_folder):
                for file in files:
                    if file.endswith((".usd", ".usda", ".usdc")):
                        exported_file = os.path.join(root, file)
                        print(f"Found exported USD file: {exported_file}")
                        return exported_file
            print(f"Warning: Could not find main exported USD file in {output_export_folder}")
            return output_export_folder # Return folder if specific file not found

        return exported_file
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
    print(f"Post-processing scene: {exported_scene_path} with prompt context: {parsed_prompt}")
    # Example: If Blender is used, launch Blender with a script
    # blender_script_path = "dnd_blender_processor.py"
    # if os.path.exists(blender_script_path):
    #     subprocess.run(["blender", "-b", exported_scene_path, "--python", blender_script_path])
    # else:
    #     print(f"Blender post-processing script {blender_script_path} not found.")
    print("Post-processing step (placeholder).")


# --- Main Function ---
def generate_battlemap(prompt: str, scene_name: str = None):
    """
    Generates a D&D battlemap based on a text prompt.
    """
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
        generator_module, gin_files, override_params = select_infinigen_config(parsed_elements)
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
        post_process_scene(exported_scene_file, parsed_elements)

        print(f"Battlemap '{scene_name}' generation complete. Main file: {exported_scene_file}")
        return exported_scene_file

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
    prompt_forest_cave = "a forest with a cave"
    battlemap_fc = generate_battlemap(prompt_forest_cave, scene_name="forest_cave_test")
    if battlemap_fc:
        print(f"Generated forest_cave_test: {battlemap_fc}")
    else:
        print(f"Failed to generate forest_cave_test.")

    # You would then take the exported_scene_file (e.g., a .usd or .glb file)
    # and load it into Blender or your Three.js application.