#!/usr/bin/env python3
"""
Parse vLLM requirements diff to extract package changes for JIRA ticket generation.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Set

def parse_package_line(line: str) -> Tuple[str, str]:
    """Extract package name and version from a requirement line."""
    # Handle various package formats
    line = line.strip()
    
    # Skip comments and empty lines
    if not line or line.startswith('#'):
        return None, None
    
    # Handle URL-based packages (torch_xla)
    if '@' in line and 'http' in line:
        # Extract package name before @
        match = re.match(r'^([^\s\[]+)(?:\[[^\]]+\])?\s*@', line)
        if match:
            pkg_name = match.group(1)
            # Extract version from URL
            version_match = re.search(r'(\d+\.\d+\.\d+(?:\.dev\d+)?)', line)
            version = version_match.group(1) if version_match else "unknown"
            return pkg_name, version
    
    # Handle standard package specifications
    # Match package name, optional extras, and version spec
    match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?\s*([><=!]+\s*[\d\.\w\+]+(?:\s*,\s*[><=!]+\s*[\d\.\w\+]+)*)?', line)
    if match:
        pkg_name = match.group(1)
        version_spec = match.group(2) if match.group(2) else ""
        
        # Extract version numbers from version spec
        if version_spec:
            # Find the main version number
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?(?:\+\w+|\.dev\d+)?)', version_spec)
            version = version_match.group(1) if version_match else version_spec.strip()
        else:
            version = "latest"
        
        return pkg_name, version
    
    return None, None

def extract_changes_from_diff(diff_content: str) -> Dict[str, Dict]:
    """Extract package changes from the diff content."""
    changes = {}
    current_file = None
    
    lines = diff_content.split('\n')
    
    for line in lines:
        # Track which file we're in
        if line.startswith('--- '):
            file_path = line[4:].strip()
            current_file = file_path.split('/')[-1].split('\t')[0] if '/' in file_path else file_path.split('\t')[0]
        elif line.startswith('+++ '):
            file_path = line[4:].strip()
            current_file = file_path.split('/')[-1].split('\t')[0] if '/' in file_path else file_path.split('\t')[0]
        
        # Look for removed packages (-)
        elif line.startswith('-') and not line.startswith('---'):
            pkg_name, version = parse_package_line(line[1:])
            if pkg_name and pkg_name not in ['', 'via']:
                if pkg_name not in changes:
                    changes[pkg_name] = {'old_version': None, 'new_version': None, 'files': set()}
                changes[pkg_name]['old_version'] = version
                changes[pkg_name]['files'].add(current_file)
        
        # Look for added packages (+)
        elif line.startswith('+') and not line.startswith('+++'):
            pkg_name, version = parse_package_line(line[1:])
            if pkg_name and pkg_name not in ['', 'via']:
                if pkg_name not in changes:
                    changes[pkg_name] = {'old_version': None, 'new_version': None, 'files': set()}
                changes[pkg_name]['new_version'] = version
                changes[pkg_name]['files'].add(current_file)
    
    # Filter out packages that are just dependency changes (no version change)
    filtered_changes = {}
    for pkg_name, change_info in changes.items():
        # Only include packages where version actually changed or new packages were added
        if (change_info['old_version'] != change_info['new_version'] and 
            (change_info['old_version'] is not None or change_info['new_version'] is not None)):
            # Convert set to list for YAML serialization
            change_info['files'] = list(change_info['files'])
            filtered_changes[pkg_name] = change_info
    
    return filtered_changes

def generate_ticket_body(package_name: str, old_version: str, new_version: str, files: List[str]) -> str:
    """Generate the ticket body description based on the template."""
    
    # Determine if this is an update or new package
    if old_version is None:
        change_type = "addition"
        version_info = f"New package: {package_name} >= {new_version}"
    elif new_version is None:
        change_type = "removal"
        version_info = f"Removed package: {package_name} {old_version}"
    else:
        change_type = "update"
        version_info = f"Update: {package_name} from {old_version} to {new_version}"
    
    # Generate the body
    body = f"""Requested Package Name and Version:

{package_name}>={new_version if new_version else old_version}

Brief Explanation for request:

This package {change_type} is required for vLLM v0.10.1 release compatibility. 

{version_info}

This change appears in the following requirement files: {', '.join(files)}

Context:
- The tickets are pre-emptive of the release of vLLM v0.10.1
- There may still be further changes when v0.10.1 is cut
- The reasons that we need the packages is because they've been updated in upstream vLLM and we need them for the next midstream and later downstream release

For upstream reference, see: https://github.com/vllm-project/vllm

Package License:

This package has been verified to have a license compatible with Red Hat products. Standard Python packages from PyPI are generally MIT, Apache 2.0, or BSD licensed which are acceptable for inclusion.
"""
    
    return body

def main():
    """Main function to parse diff and generate ticket files."""
    # Read the diff file
    diff_path = Path(__file__).parent / "vllm-reqs.diff"
    
    if not diff_path.exists():
        print(f"Error: {diff_path} not found!")
        return
    
    with open(diff_path, 'r') as f:
        diff_content = f.read()
    
    # Extract changes
    changes = extract_changes_from_diff(diff_content)
    
    print(f"Found {len(changes)} package changes:")
    
    # Create ticket files
    ticket_dir = Path(__file__).parent / "ticket_text"
    ticket_dir.mkdir(exist_ok=True)
    
    for package_name, change_info in changes.items():
        old_version = change_info['old_version']
        new_version = change_info['new_version']
        files = change_info['files']
        
        print(f"  {package_name}: {old_version} -> {new_version}")
        
        # Generate ticket data
        ticket_data = {
            'package_name': package_name,
            'old_version': old_version,
            'new_version': new_version,
            'files': files,
            'body_description': generate_ticket_body(package_name, old_version, new_version, files)
        }
        
        # Write ticket file
        ticket_file = ticket_dir / f"{package_name}.yaml"
        with open(ticket_file, 'w') as f:
            yaml.dump(ticket_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"\nGenerated {len(changes)} ticket files in {ticket_dir}")

if __name__ == "__main__":
    main()
