import os
import re
from pathlib import Path

def is_excluded(path):
    excluded_dirs = {'.venv', '.tmp_ci_venv', 'node_modules', '__pycache__', '.pytest_cache', '.git'}
    return any(part in excluded_dirs for part in path.parts)

def check_link(link, current_dir, root_dir):
    link = link.split('#')[0].split('?')[0]
    if not link or link.startswith(('http://', 'https://', 'mailto:', 'ftp:')):
        return True
    try:
        target = (current_dir / link).resolve()
        if target.exists():
            return True
        target_abs = (root_dir / link.lstrip('/')).resolve()
        if target_abs.exists():
            return True
    except Exception:
        pass
    return False

def is_file_like(token):
    if re.match(r'^[a-zA-Z0-9_\-\./\\]+\.[a-z0-1]+$', token):
        if not token.startswith(('http', 'www')) and len(token) > 3:
            return True
    return False

def main():
    root_dir = Path.cwd()
    readme_files = []
    
    # Use os.walk for better performance/reliability on large trees
    for root, dirs, files in os.walk(root_dir):
        path_root = Path(root)
        if is_excluded(path_root):
            dirs[:] = [] # skip this directory tree
            continue
            
        for name in files:
            if name.lower().startswith('readme') or 'TEMP_WILL_BE_DELETED' in name:
                readme_files.append(path_root / name)

    broken_links = {}
    missing_tokens = {}
    md_link_re = re.compile(r'\[.*?\]\((.*?)\)')
    
    for readme in readme_files:
        try:
            content = readme.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
            
        rel_path = readme.relative_to(root_dir)
        links = md_link_re.findall(content)
        broken = [l for l in links if not check_link(l, readme.parent, root_dir)]
        if broken:
            broken_links[str(rel_path)] = broken
            
        tokens = re.split(r'[\s"\'\(\)\[\]\{\}\<\>]', content)
        missing = []
        for t in tokens:
            if is_file_like(t):
                if not check_link(t, readme.parent, root_dir):
                    missing.append(t)
        if missing:
            missing_tokens[str(rel_path)] = missing

    print(f"Total READMEs found: {len(readme_files)}")
    print("\n--- Files with Broken Markdown Links ---")
    for path, links in broken_links.items():
        print(f"{path}: {len(links)} broken links. Examples: {links[:3]}")

    print("\n--- Top Files with Missing File-like Tokens ---")
    sorted_missing = sorted(missing_tokens.items(), key=lambda x: len(x[1]), reverse=True)
    for path, tokens in sorted_missing[:10]:
        print(f"{path}: {len(tokens)} missing. Examples: {list(set(tokens))[:3]}")

if __name__ == '__main__':
    main()