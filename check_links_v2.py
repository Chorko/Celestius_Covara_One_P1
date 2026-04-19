import os
import re

root = os.getcwd()
exclude_dirs = {".git", ".venv", ".tmp_ci_venv", "node_modules", "__pycache__", ".pytest_cache"}
temp_dir = "TEMP_WILL_BE_DELETED"

readme_files = []
for dirpath, dirnames, filenames in os.walk(root):
    # Skip excluded directories
    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
    # Also skip if any parent is an exclude_dir (os.walk doesn't automatically skip subtrees of excluded dirs if we don't modify dirnames in place, but we are)
    for f in filenames:
        if f.lower().startswith("readme"):
            readme_files.append(os.path.join(dirpath, f))

broken_links_by_file = {}
stats = {"temp": 0, "outside": 0}

# Markdown link pattern: [text](target)
link_pattern = re.compile(r"\[.*?\]\((.*?)\)")

for readme in readme_files:
    rel_path = os.path.relpath(readme, root)
    if temp_dir in rel_path.split(os.sep):
        stats["temp"] += 1
    else:
        stats["outside"] += 1
    
    broken_in_file = []
    try:
        with open(readme, "r", encoding="utf-8") as f:
            content = f.read()
            links = link_pattern.findall(content)
            for target in links:
                # Clean target (remove anchors)
                target_clean = target.split("#")[0]
                # Filter out external/special links
                if not target_clean or any(target_clean.startswith(p) for p in ["http://", "https://", "mailto:", "tel:", "javascript:", "data:"]):
                    continue
                
                # Logic for local path
                if target_clean.startswith("/"):
                    # Relative to root
                    check_path = os.path.join(root, target_clean.lstrip("/"))
                else:
                    # Relative to file
                    check_path = os.path.join(os.path.dirname(readme), target_clean)
                
                # Check existence
                if not os.path.exists(check_path):
                    broken_in_file.append(target)
    except Exception as e:
        # Silently skip read errors (binary files etc)
        pass
    
    if broken_in_file:
        broken_links_by_file[rel_path] = sorted(list(set(broken_in_file)))

print(f"Total README files scanned: {len(readme_files)}")
print(f"Total files with broken markdown links: {len(broken_links_by_file)}")
print("Files with broken links:")
for f, links in sorted(broken_links_by_file.items()):
    print(f"  {f}: {links}")
print(f"Breakdown counts: TEMP_WILL_BE_DELETED: {stats['temp']}, Outside: {stats['outside']}")
