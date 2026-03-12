import os
import re
import glob
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP

# --- CONFIGURATION ---
# Adjust these paths to match your system
JUCE_PATH = "E:/JUCE"
MODULES_PATH = os.path.join(JUCE_PATH, "modules")
EXAMPLES_PATH = os.path.join(JUCE_PATH, "examples")
JUCE_XML_PATH = os.path.join(JUCE_PATH, "xml")

# --- GLOBAL STATE ---
current_project_path = None
class_map = {}  # Maps "AudioBuffer" -> "classjuce_1_1AudioBuffer.xml"

mcp = FastMCP("juce-architect-ultimate")

# ==========================================
#  INITIALIZATION (XML INDEXING)
# ==========================================
def load_xml_index():
    """Parses the main Doxygen index to map ClassNames to XML files."""
    global class_map
    index_path = os.path.join(JUCE_XML_PATH, "index.xml")
    
    if not os.path.exists(index_path):
        print(f"Warning: Doxygen XML index not found at {index_path}.")
        print("Documentation features will be limited. Please run Doxygen.")
        return

    try:
        tree = ET.parse(index_path)
        root = tree.getroot()
        count = 0
        for compound in root.findall("compound"):
            kind = compound.get("kind")
            if kind in ["class", "struct"]:
                name = compound.find("name").text
                refid = compound.get("refid")
                # Handle names like "juce::AudioBuffer" -> "AudioBuffer"
                simple_name = name.split("::")[-1]
                class_map[simple_name.lower()] = f"{refid}.xml"
                count += 1
        print(f"Success: Indexed {count} classes from Doxygen XML.")
    except Exception as e:
        print(f"Error loading XML index: {e}")

# Run once on startup
load_xml_index()

# ==========================================
#  PART 1: PROJECT CONTEXT (Your Local Work)
# ==========================================

@mcp.tool()
def set_active_project(path_to_project_root: str) -> str:
    """
    Sets the active JUCE project directory for the current session.
    Example: set_active_project("E:/Dev/CanonKey_old")
    """
    global current_project_path
    clean_path = os.path.abspath(path_to_project_root)
    
    if not os.path.exists(clean_path):
        return f"Error: Path does not exist: {clean_path}"
    
    # Validation
    has_jucer = any(f.endswith(".jucer") for f in os.listdir(clean_path))
    has_source = os.path.exists(os.path.join(clean_path, "Source"))
    
    if not (has_jucer or has_source):
        return f"Warning: Path set to '{clean_path}', but it lacks a .jucer file or Source folder."
        
    current_project_path = clean_path
    return f"Active project set to: {os.path.basename(clean_path)}"

@mcp.tool()
def list_project_files() -> str:
    """Lists .h/.cpp files in the active project's Source directory."""
    global current_project_path
    if not current_project_path:
        return "Error: No project selected. Use 'set_active_project' first."
    
    source_dir = os.path.join(current_project_path, "Source")
    search_root = source_dir if os.path.exists(source_dir) else current_project_path
    
    file_list = []
    for root, _, files in os.walk(search_root):
        if "Builds" in root or "JuceLibraryCode" in root: continue
        for file in files:
            if file.endswith((".h", ".cpp", ".mm")):
                rel_path = os.path.relpath(os.path.join(root, file), current_project_path)
                file_list.append(rel_path)
                
    if not file_list: return "No source files found."
    return "Project Files:\n" + "\n".join(sorted(file_list))

@mcp.tool()
def read_project_file(partial_name: str) -> str:
    """Reads a specific file from the active project."""
    global current_project_path
    if not current_project_path:
        return "Error: No project selected."

    target_path = None
    for root, _, files in os.walk(current_project_path):
        if "JuceLibraryCode" in root or "Builds" in root: continue
        for file in files:
            if file.lower() == partial_name.lower():
                target_path = os.path.join(root, file)
                break
        if target_path: break
    
    if not target_path: return f"File '{partial_name}' not found."

    try:
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            return f"--- {os.path.basename(target_path)} ---\n{f.read()}"
    except Exception as e:
        return f"Error reading file: {e}"

# ==========================================
#  PART 2: DOCUMENTATION (XML Powered)
# ==========================================

@mcp.resource("juce://docs/{class_name}")
def get_structured_docs(class_name: str) -> str:
    """
    Returns full API documentation for a class (methods, inheritance) from XML.
    """
    xml_file = class_map.get(class_name.lower())
    if not xml_file:
        return f"# Error\nClass '{class_name}' not found in Doxygen index. (Did you run Doxygen?)"

    full_path = os.path.join(JUCE_XML_PATH, xml_file)
    try:
        tree = ET.parse(full_path)
        root = tree.getroot()
        compound = root.find("compounddef")
        
        output = []
        name = compound.find("compoundname").text
        brief = compound.find("briefdescription/para")
        brief_txt = brief.text if brief is not None else ""
        
        output.append(f"# {name}\n\n{brief_txt}\n")
        
        # Inheritance
        bases = compound.findall("basecompoundref")
        if bases:
            output.append("### Inherits From:")
            for base in bases:
                output.append(f"* {base.text}")
            output.append("")

        # Methods
        output.append("### Public Methods")
        for section in compound.findall("sectiondef"):
            if section.get("kind") == "public-func":
                for member in section.findall("memberdef"):
                    func_name = member.find("name").text
                    func_type = member.find("type").text or "void"
                    
                    # Params
                    params = []
                    for param in member.findall("param"):
                        p_type = "".join(param.find("type").itertext()) # Handles complex types better
                        p_decl = param.find("declname")
                        p_name = p_decl.text if p_decl is not None else ""
                        params.append(f"{p_type} {p_name}".strip())
                    
                    sig = f"`{func_type} {func_name} ({', '.join(params)})`"
                    
                    # Description
                    desc_elem = member.find("detaileddescription/para")
                    desc = "".join(desc_elem.itertext()) if desc_elem is not None else ""
                    
                    output.append(f"#### {func_name}\n{sig}\n{desc[:300]}..." if len(desc) > 300 else f"{desc}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Error parsing XML: {e}"

@mcp.tool()
def search_classes(query: str) -> str:
    """Search for JUCE classes in the index."""
    matches = [k for k in class_map.keys() if query.lower() in k]
    if not matches: return "No matches found in XML index."
    return "\n".join(matches[:25])

# ==========================================
#  PART 3: EXAMPLES & RAW ACCESS (Tutorials)
# ==========================================

@mcp.tool()
def search_examples(topic: str) -> str:
    """
    Search the JUCE examples folder. Great for finding implementation patterns.
    """
    matches = []
    for root, _, files in os.walk(EXAMPLES_PATH):
        for file in files:
            if file.endswith((".h", ".cpp")) and topic.lower() in file.lower():
                rel_path = os.path.relpath(os.path.join(root, file), EXAMPLES_PATH)
                matches.append(rel_path)
    
    if not matches: return "No examples found."
    return "Found example files:\n" + "\n".join(matches[:15])

@mcp.tool()
def read_raw_file(path: str, source: str = "modules") -> str:
    """
    Read a raw file from 'modules' or 'examples' if XML docs aren't enough.
    source: 'modules' or 'examples'
    """
    base = MODULES_PATH if source == "modules" else EXAMPLES_PATH
    full_path = os.path.join(base, path)
    
    # Security check
    if not os.path.commonpath([full_path, base]) == base:
        return "Error: Access denied."

    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()[:20000] # Limit size
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    mcp.run()