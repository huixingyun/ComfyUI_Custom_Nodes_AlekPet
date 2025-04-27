import os
import subprocess
import sys
import shutil
import __main__
import re
import threading
import ast
from concurrent.futures import ThreadPoolExecutor

python = sys.executable

# User extension files in custom_nodes
extension_folder = os.path.dirname(os.path.realpath(__file__))

# ComfyUI folders web
folder_web = os.path.join(os.path.dirname(os.path.realpath(__main__.__file__)), "web")
folder_comfyui_web_extensions = os.path.join(folder_web, "extensions")
folder__web_lib = os.path.join(folder_web, "lib")

# Directory for web extensions specific to this node pack
web_extensions_dir_name = "web_alekpet_nodes"
web_extensions_dir_path = os.path.join(extension_folder, web_extensions_dir_name)


# Debug mode
DEBUG = False

module_name_cut_version = re.compile("[>=<]")


def get_version_extension():
    version = ""
    toml_file = os.path.join(extension_folder, "pyproject.toml")
    if os.path.isfile(toml_file):
        try:
            with open(toml_file, "r") as v:
                version = list(
                    filter(lambda l: l.startswith("version"), v.readlines())
                )[0]
                version = version.split("=")[1].replace('"', "").strip()
                return f" \033[1;34mv{version}\033[0m\033[1;35m"
        except Exception as e:
            print(e)

    return version


def log(*text):
    if DEBUG:
        print("".join(map(str, text)))


def information(datas):
    for info in datas:
        if not DEBUG:
            print(info, end="\r", flush=True)


def printColorInfo(text, color="\033[92m"):
    CLEAR = "\033[0m"
    print(f"{color}{text}{CLEAR}")

def get_classes(code):
    tree = ast.parse(code)
    return [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and "Node" in n.name
    ]

def getNamesNodesInsidePyFile(nodeElement):
    node_folder = os.path.join(extension_folder, nodeElement)
    cls_names = []
    for f in os.listdir(node_folder):
        ext = os.path.splitext(f)
        if (
            os.path.isfile(os.path.join(node_folder, f))
            and not f.startswith("__")
            and ext[1] == ".py"
            and ext[0] != "__init__"
        ):
            try:
                with open(os.path.join(node_folder, f), "r", encoding='utf-8') as pyf:
                    cls_names.extend(get_classes(pyf.read()))
            except Exception as e:
                 print(f"Error reading file {f}: {e}")
    return cls_names


def checkFolderIsset():
    log(f"*  Check and make not isset dirs...")
    if not os.path.exists(web_extensions_dir_path):
        log(f"* Dir <{web_extensions_dir_name}> is not found, create...")
        os.makedirs(web_extensions_dir_path)
        log(f"* Dir <{web_extensions_dir_name}> created!")


def module_install(commands, cwd="."):
    result = subprocess.Popen(
        commands,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding='utf-8',
        errors='replace'
    )
    out = threading.Thread(target=information, args=(result.stdout,))
    err = threading.Thread(target=information, args=(result.stderr,))
    out.start()
    err.start()
    out.join()
    err.join()

    return result.wait()


def get_installed_modules():
    result = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.split("==")[0].lower() for line in result.stdout.splitlines()}


def checkModules(nodeElement, installed_modules):
    file_requir = os.path.join(extension_folder, nodeElement, "requirements.txt")
    if os.path.exists(file_requir):
        log("  -> File 'requirements.txt' found!")
        try:
             with open(file_requir, 'r', encoding='utf-8') as f:
                required_modules = {
                    module_name_cut_version.split(line.strip())[0].lower()
                    for line in f
                    if line.strip() and not line.startswith("#")
                }

             modules_to_install = required_modules - installed_modules

             if modules_to_install:
                 print(f"  -> Installing dependencies for {nodeElement}: {', '.join(modules_to_install)}")
                 module_install(
                     [sys.executable, "-m", "pip", "install", *modules_to_install]
                 )
             else:
                 print(f"  -> Dependencies for {nodeElement} already satisfied.")
        except Exception as e:
            print(f"Error processing requirements for {nodeElement}: {e}")


nodes_list_dict = {}


def install_node_web_files(nodeElement):
    log(f"* Copying web files for <{nodeElement}>...")

    extensions_dirs_copy = ["js", "css", "assets", "lib", "fonts"]
    for dir_name in extensions_dirs_copy:
        folder_curr = os.path.join(extension_folder, nodeElement, dir_name)
        if os.path.exists(folder_curr) and os.path.isdir(folder_curr):
            # Determine destination path
            if dir_name == 'js':
                # JS files often go into a subdirectory named after the node or directly into the web extensions dir
                folder_curr_dist = os.path.join(web_extensions_dir_path, 'js')
            else:
                 folder_curr_dist = os.path.join(web_extensions_dir_path, dir_name)

            # Ensure the destination directory exists
            os.makedirs(folder_curr_dist, exist_ok=True)

            log(f"  -> Copying '{dir_name}' from '{folder_curr}' to '{folder_curr_dist}'")
            try:
                shutil.copytree(folder_curr, folder_curr_dist, dirs_exist_ok=True)
            except Exception as e:
                 print(f"Error copying {dir_name} for {nodeElement}: {e}")

def installNodes():
    global nodes_list_dict
    log(f"\n-------> AlekPet Node Installing [DEBUG] <-------")
    printColorInfo(
        f"### [START] ComfyUI AlekPet Nodes Installation{get_version_extension()} ###", "\033[1;35m"
    )

    # Remove files in lib directory (if necessary, depends on node requirements)
    libfiles = ["fabric.js"]
    for file in libfiles:
        filePath = os.path.join(folder__web_lib, file)
        if os.path.isfile(filePath):
             try:
                 os.remove(filePath)
                 log(f"Removed old file: {filePath}")
             except Exception as e:
                 print(f"Error removing old file {filePath}: {e}")


    # Remove old web extensions folder if exist
    oldDirNodes = os.path.join(folder_comfyui_web_extensions, "AlekPet_Nodes")
    if os.path.exists(oldDirNodes):
        try:
             shutil.rmtree(oldDirNodes)
             log(f"Removed old web directory: {oldDirNodes}")
        except Exception as e:
             print(f"Error removing old web directory {oldDirNodes}: {e}")


    # Clear or ensure target web extensions directory exists
    if os.path.exists(web_extensions_dir_path):
         try:
             shutil.rmtree(web_extensions_dir_path)
             log(f"Cleared existing web directory: {web_extensions_dir_path}")
         except Exception as e:
             print(f"Error clearing web directory {web_extensions_dir_path}: {e}")

    checkFolderIsset()

    installed_modules = set()
    try:
        installed_modules = get_installed_modules()
    except Exception as e:
        print(f"Warning: Could not retrieve installed modules. Dependencies might not be checked correctly. Error: {e}")


    nodes = []
    for nodeElement in os.listdir(extension_folder):
        if (
            os.path.isdir(os.path.join(extension_folder, nodeElement))
            and not nodeElement.startswith("__")
            and not nodeElement.startswith(".")
            and nodeElement != web_extensions_dir_name # Exclude the web dir itself
            and os.path.exists(os.path.join(extension_folder, nodeElement, "__init__.py")) # Check if it might be a node package
            or (nodeElement.endswith("Node") and os.path.isdir(os.path.join(extension_folder, nodeElement))) # Keep original heuristic as fallback
        ):
             # Basic check for a node structure (e.g., contains .py files)
            has_py_files = any(f.endswith('.py') for f in os.listdir(os.path.join(extension_folder, nodeElement)))
            if not has_py_files and not os.path.exists(os.path.join(extension_folder, nodeElement, "requirements.txt")):
                 log(f"Skipping directory '{nodeElement}', does not appear to be a node package.")
                 continue

            nodes_list_dict[nodeElement] = {
                "error": None,
                "status": "[92m[Pending]"
            }
            nodes.append(nodeElement)

    print(f"Found {len(nodes)} potential node packages to process.")

    # Process nodes sequentially for clearer output and dependency handling
    for nodeElement in nodes:
        print(f"Processing node package: {nodeElement}")
        clsNodes = getNamesNodesInsidePyFile(nodeElement)
        clsNodesText = "[93m" + ", ".join(clsNodes) + "[0m" if clsNodes else " (No specific node classes found in top-level .py files)"
        printColorInfo(f"Node -> {nodeElement}: {clsNodesText}")

        nodes_list_dict[nodeElement].update({"nodes": clsNodes})

        try:
             # 1. Install web files
             install_node_web_files(nodeElement)

             # 2. Check and install dependencies
             checkModules(nodeElement, installed_modules)

             nodes_list_dict[nodeElement]["status"] = "[92m[Installed]"
             printColorInfo(f"Node -> {nodeElement}: [92m[Success]")

        except Exception as e:
             nodes_list_dict[nodeElement]["error"] = str(e)
             nodes_list_dict[nodeElement]["status"] = "[1;31;40m[Failed]"
             printColorInfo(f"Node -> {nodeElement}: [1;31;40m[Failed] - Error: {e}", "\033[1;31m")


    # Final Summary
    printColorInfo(f"\n--- Installation Summary ---")
    failed_nodes_text = ""
    successful_nodes = 0
    failed_nodes = 0

    for node, data in nodes_list_dict.items():
        status = data.get("status", "[93m[Unknown]")
        printColorInfo(f" {node}: {status}")
        if data.get("error"):
            failed_nodes += 1
            failed_nodes_text += f"  - {node}: {data.get('error')}\n"
        elif status == "[92m[Installed]":
             successful_nodes +=1

    if failed_nodes > 0:
        printColorInfo(f"\n{failed_nodes} node package(s) encountered errors during installation:", "\033[1;31m")
        print(failed_nodes_text)
        printColorInfo(f"Please check the errors above. Some nodes might not work correctly.", "\033[1;31m")

    printColorInfo(f"Successfully processed {successful_nodes} node package(s).")
    printColorInfo(f"### [END] ComfyUI AlekPet Nodes Installation ###", "\033[1;35m")

# --- Main execution ---
if __name__ == "__main__":
    installNodes()
