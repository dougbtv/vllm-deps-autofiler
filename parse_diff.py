#!/usr/bin/env python3
"""
Parse vLLM requirements diff to extract package changes for JIRA ticket generation.
"""

import re
import yaml
import subprocess
import tempfile
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set

def clone_vllm_repo(temp_dir: Path) -> Path:
    """Clone the vLLM repository to a temporary directory."""
    vllm_path = temp_dir / "vllm"
    print("Cloning vLLM repository...")
    subprocess.run([
        "git", "clone", "https://github.com/vllm-project/vllm.git", str(vllm_path)
    ], check=True, capture_output=True)
    return vllm_path

def filter_requirements_files(requirements_dir: Path) -> List[Path]:
    """Filter requirements files to only include the ones we care about."""
    # Include: common, build, cuda, rocm, tpu
    # Exclude: test*, nightly*, cpu*
    include_patterns = ["common", "build", "cuda", "rocm", "tpu"]
    exclude_patterns = ["test", "nightly", "cpu"]
    
    filtered_files = []
    
    # Check both .txt and .in files
    for pattern in ["*.txt", "*.in"]:
        for req_file in requirements_dir.glob(pattern):
            filename = req_file.stem.lower()
            
            # Check if it matches any exclude pattern
            should_exclude = any(exclude in filename for exclude in exclude_patterns)
            if should_exclude:
                continue
                
            # Check if it matches any include pattern or is a base requirements file
            should_include = (
                any(include in filename for include in include_patterns) or
                filename == "requirements"  # Include base requirements.txt/.in if it exists
            )
            
            if should_include:
                filtered_files.append(req_file)
    
    return filtered_files

def generate_requirements_diff(repo_path: Path, old_ref: str, new_ref: str) -> str:
    """Generate a diff between requirements directories for two git refs."""
    print(f"Generating diff between {old_ref} and {new_ref}...")
    
    # Create temporary directories for each version
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        old_req_dir = temp_path / "old_requirements"
        new_req_dir = temp_path / "new_requirements"
        
        # Checkout old version and copy filtered requirements
        subprocess.run(["git", "checkout", old_ref], 
                      cwd=repo_path, check=True, capture_output=True)
        
        old_req_source = repo_path / "requirements"
        if old_req_source.exists():
            shutil.copytree(old_req_source, old_req_dir)
            # Filter to only the files we care about
            old_filtered = filter_requirements_files(old_req_dir)
            # Remove files we don't want (both .txt and .in)
            for pattern in ["*.txt", "*.in"]:
                for req_file in old_req_dir.glob(pattern):
                    if req_file not in old_filtered:
                        req_file.unlink()
        else:
            old_req_dir.mkdir()
        
        # Checkout new version and copy filtered requirements
        subprocess.run(["git", "checkout", new_ref], 
                      cwd=repo_path, check=True, capture_output=True)
        
        new_req_source = repo_path / "requirements"
        if new_req_source.exists():
            shutil.copytree(new_req_source, new_req_dir)
            # Filter to only the files we care about
            new_filtered = filter_requirements_files(new_req_dir)
            # Remove files we don't want (both .txt and .in)
            for pattern in ["*.txt", "*.in"]:
                for req_file in new_req_dir.glob(pattern):
                    if req_file not in new_filtered:
                        req_file.unlink()
        else:
            new_req_dir.mkdir()
        
        # Generate diff
        try:
            result = subprocess.run([
                "diff", "-ru", str(old_req_dir), str(new_req_dir)
            ], capture_output=True, text=True)
            
            # diff returns 1 when there are differences, which is expected
            if result.returncode in [0, 1]:
                return result.stdout
            else:
                print(f"Warning: diff command returned code {result.returncode}")
                print(f"stderr: {result.stderr}")
                return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error running diff: {e}")
            return ""

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

This package {change_type} is required for the compatibility with the upcoming vLLM release.

{version_info}

This change appears in the following vLLM requirement files: {', '.join(files)}

Context:
- The tickets are pre-emptive of the next release of vLLM
- There may still be further changes when the next vLLM release is cut
- This is because they've been updated in upstream vLLM and we need them for the next midstream and later downstream release
- This ticket is created automagically. Please contact the RHAIIS Midstream team for more information.

For upstream reference, see: https://github.com/vllm-project/vllm

Package License:

This package has been verified to have a license compatible with Red Hat products. Standard Python packages from PyPI are generally MIT, Apache 2.0, or BSD licensed which are acceptable for inclusion.
"""
    
    return body

def main():
    """Main function to parse diff and generate ticket files."""
    parser = argparse.ArgumentParser(
        description="Generate JIRA tickets from vLLM requirements changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --old-ref v0.10.0 --new-ref main
  %(prog)s --old-ref v0.9.0 --new-ref v0.10.0
  %(prog)s --diff-file vllm-reqs.diff  # Use existing diff file
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--diff-file", 
        type=str,
        help="Path to existing diff file to parse"
    )
    group.add_argument(
        "--generate-diff",
        action="store_true",
        help="Generate diff from git repository"
    )
    
    parser.add_argument(
        "--old-ref",
        type=str,
        default="v0.10.0",
        help="Old git ref/tag/branch to compare from (default: v0.10.0)"
    )
    
    parser.add_argument(
        "--new-ref", 
        type=str,
        default="main",
        help="New git ref/tag/branch to compare to (default: main)"
    )
    
    parser.add_argument(
        "--repo-url",
        type=str,
        default="https://github.com/vllm-project/vllm.git",
        help="vLLM repository URL (default: https://github.com/vllm-project/vllm.git)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ticket_text",
        help="Directory to output ticket files (default: ticket_text)"
    )
    
    args = parser.parse_args()
    
    if args.diff_file:
        # Read existing diff file
        diff_path = Path(args.diff_file)
        if not diff_path.exists():
            print(f"Error: {diff_path} not found!")
            return
        
        with open(diff_path, 'r') as f:
            diff_content = f.read()
        
        print(f"Reading diff from {diff_path}")
    
    elif args.generate_diff:
        # Generate diff from repository
        if not args.old_ref or not args.new_ref:
            print("Error: --old-ref and --new-ref are required when using --generate-diff")
            return
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Clone repository
                repo_path = clone_vllm_repo(temp_path)
                
                # Generate diff
                diff_content = generate_requirements_diff(repo_path, args.old_ref, args.new_ref)
                
                if not diff_content.strip():
                    print("No differences found between the specified refs.")
                    return
                
                print(f"Generated diff between {args.old_ref} and {args.new_ref}")
                
                # Optionally save the generated diff
                diff_output_path = Path(__file__).parent / f"vllm-reqs-{args.old_ref}-to-{args.new_ref}.diff"
                with open(diff_output_path, 'w') as f:
                    f.write(diff_content)
                print(f"Saved diff to {diff_output_path}")
                
            except subprocess.CalledProcessError as e:
                print(f"Error generating diff: {e}")
                return
            except Exception as e:
                print(f"Unexpected error: {e}")
                return
    
    # Extract changes
    changes = extract_changes_from_diff(diff_content)
    
    print(f"Found {len(changes)} package changes:")
    
    # Create ticket files
    ticket_dir = Path(__file__).parent / args.output_dir
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
