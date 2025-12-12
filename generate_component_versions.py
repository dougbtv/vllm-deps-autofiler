#!/usr/bin/env python3
"""
Extract component version information from vLLM repository for RHAI Release spreadsheet.

This tool clones a vLLM repository at a specific tag/ref and extracts version information
for all components needed in the "RHAI Release to Component Version Mapping" spreadsheet
(rows 16-54).
"""

import re
import subprocess
import tempfile
import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple


def clone_vllm_repo(temp_dir: Path, repo_url: str, ref: str) -> Path:
    """Clone the vLLM repository to a temporary directory and checkout ref."""
    vllm_path = temp_dir / "vllm"
    print(f"Cloning vLLM repository from {repo_url}...", file=sys.stderr)
    subprocess.run([
        "git", "clone", repo_url, str(vllm_path)
    ], check=True, capture_output=True)

    print(f"Checking out {ref}...", file=sys.stderr)
    subprocess.run([
        "git", "checkout", ref
    ], cwd=vllm_path, check=True, capture_output=True)

    return vllm_path


def safe_extract(extraction_func, *args, default="[tbd]", **kwargs):
    """Safely execute extraction function with fallback to default."""
    try:
        result = extraction_func(*args, **kwargs)
        return result if result is not None else default
    except Exception as e:
        print(f"Warning: {extraction_func.__name__} failed: {e}", file=sys.stderr)
        return default


def parse_dockerfile_arg(repo_path: Path, dockerfile: str, arg_name: str) -> Optional[str]:
    """Parse ARG variable from Dockerfile."""
    dockerfile_path = repo_path / "docker" / dockerfile
    if not dockerfile_path.exists():
        return None

    with open(dockerfile_path, 'r') as f:
        for line in f:
            # Match: ARG ARG_NAME=value or ARG ARG_NAME="value"
            match = re.match(rf'^\s*ARG\s+{arg_name}=(.+)$', line.strip())
            if match:
                value = match.group(1).strip('"').strip("'")
                return value
    return None


def parse_script_var(repo_path: Path, script_path: str, var_name: str) -> Optional[str]:
    """Parse shell variable from script file."""
    full_path = repo_path / script_path
    if not full_path.exists():
        return None

    with open(full_path, 'r') as f:
        for line in f:
            # Match: VAR_NAME=${VAR_NAME:-"value"}
            match = re.match(rf'{var_name}=\$\{{{var_name}:-"([^"]+)"\}}', line.strip())
            if match:
                return match.group(1)
            # Match: VAR_NAME="value"
            match = re.match(rf'{var_name}="([^"]+)"', line.strip())
            if match:
                return match.group(1)
            # Match: VAR_NAME=value (no quotes)
            match = re.match(rf'{var_name}=([^\s#]+)', line.strip())
            if match:
                return match.group(1)
    return None


def parse_package_line(line: str) -> Tuple[str, str]:
    """
    Extract package name and version from a requirement line.
    Reused from parse_diff.py with modifications.
    """
    line = line.strip()

    # Skip comments, empty lines, and pip options
    if not line or line.startswith('#') or line.startswith('--'):
        return None, None

    # Handle URL-based packages (torch_xla, git repos)
    if '@' in line and 'http' in line:
        match = re.match(r'^([^\s\[]+)(?:\[[^\]]+\])?\s*@', line)
        if match:
            pkg_name = match.group(1)

            # Extract git commit hash (40 hex characters)
            git_commit_match = re.search(r'@([0-9a-f]{40})', line)
            if git_commit_match:
                # Use short form (first 8 characters)
                version = git_commit_match.group(1)[:8]
                return pkg_name, version

            # Otherwise extract semantic version from URL
            version_match = re.search(r'(\d+\.\d+\.\d+(?:\.dev\d+)?)', line)
            version = version_match.group(1) if version_match else "unknown"
            return pkg_name, version

    # Handle standard package specifications
    match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?\s*([><=!]+\s*[\d\.\w\+]+(?:\s*,\s*[><=!]+\s*[\d\.\w\+]+)*)?', line)
    if match:
        pkg_name = match.group(1)
        version_spec = match.group(2) if match.group(2) else ""

        if version_spec:
            # Prefer lower bounds (>=) over upper bounds (<)
            lower_bound_match = re.search(r'>=?\s*(\d+\.\d+(?:\.\d+)?(?:\+\w+|\.dev\d+)?)', version_spec)
            if lower_bound_match:
                version = lower_bound_match.group(1)
            else:
                # Try exact version (==)
                exact_match = re.search(r'==\s*(\d+\.\d+(?:\.\d+)?(?:\+\w+|\.dev\d+)?)', version_spec)
                if exact_match:
                    version = exact_match.group(1)
                else:
                    # Keep full constraint if only upper bound
                    if re.match(r'^\s*<[=]?\s*[\d\.]+', version_spec.strip()):
                        version = version_spec.strip()
                    else:
                        # Fall back to any version number found
                        version_match = re.search(r'(\d+\.\d+(?:\.\d+)?(?:\+\w+|\.dev\d+)?)', version_spec)
                        version = version_match.group(1) if version_match else version_spec.strip()
        else:
            version = "latest"

        return pkg_name, version

    return None, None


def parse_requirements_file(repo_path: Path, req_file: str, package_name: str) -> Optional[str]:
    """Extract version for specific package from requirements file."""
    req_path = repo_path / "requirements" / req_file
    if not req_path.exists():
        return None

    with open(req_path, 'r') as f:
        for line in f:
            pkg_name, version = parse_package_line(line)
            if pkg_name and pkg_name.lower() == package_name.lower():
                return version
    return None


# ===== Component-Specific Extractors =====

def extract_python_version(repo_path: Path) -> str:
    """
    Extract Python version from Dockerfile.
    Note: This returns the build default (e.g., 3.12), not the RHEL-specific patch version.
    For RHEL builds, the actual version depends on the RHEL version (e.g., RHEL 9.6 uses 3.12.9).
    """
    # Try to get from Dockerfile first (gives us the build version like 3.12)
    python_ver = parse_dockerfile_arg(repo_path, "Dockerfile", "PYTHON_VERSION")
    if python_ver:
        return python_ver

    # Fallback to pyproject.toml (gives us minimum supported version)
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return "[tbd]"

    with open(pyproject_path, 'r') as f:
        for line in f:
            # Match: requires-python = ">=3.10,<3.14"
            match = re.match(r'^\s*requires-python\s*=\s*">=(\d+\.\d+)', line.strip())
            if match:
                return match.group(1)
    return "[tbd]"


def extract_cuda_version(repo_path: Path) -> str:
    """Extract CUDA version from Dockerfile."""
    version = parse_dockerfile_arg(repo_path, "Dockerfile", "CUDA_VERSION")
    return version if version else "[tbd]"


def extract_rocm_version(repo_path: Path) -> str:
    """Extract ROCM version from Dockerfile.rocm_base."""
    base_image = parse_dockerfile_arg(repo_path, "Dockerfile.rocm_base", "BASE_IMAGE")
    if base_image:
        # Extract version from: rocm/dev-ubuntu-22.04:7.1-complete
        match = re.search(r':(\d+\.\d+)', base_image)
        if match:
            return match.group(1)
    return "[tbd]"


def extract_gcc_version(repo_path: Path) -> str:
    """Extract GCC version from Dockerfile."""
    dockerfile_path = repo_path / "docker" / "Dockerfile"
    if not dockerfile_path.exists():
        return "[tbd]"

    with open(dockerfile_path, 'r') as f:
        content = f.read()
        # Look for gcc-XX or g++-XX installation
        match = re.search(r'gcc-(\d+)', content)
        if match:
            return match.group(1)
    return "[tbd]"


def extract_aiter_version(repo_path: Path) -> str:
    """Extract aiter git hash from Dockerfile.rocm_base."""
    aiter_branch = parse_dockerfile_arg(repo_path, "Dockerfile.rocm_base", "AITER_BRANCH")
    if aiter_branch:
        # Return short form (8 chars) if it's a git hash
        if re.match(r'^[0-9a-f]+$', aiter_branch):
            return aiter_branch[:8]
        return aiter_branch
    return "[tbd]"


def extract_torch_versions(repo_path: Path) -> Dict[str, str]:
    """Extract torch versions for different accelerators."""
    versions = {}

    # CUDA
    cuda_torch = parse_requirements_file(repo_path, "cuda.txt", "torch")
    versions['cuda'] = cuda_torch if cuda_torch else "[tbd]"

    # ROCM - try both rocm.txt and rocm-build.txt
    rocm_torch = parse_requirements_file(repo_path, "rocm-build.txt", "torch")
    if not rocm_torch:
        rocm_torch = parse_requirements_file(repo_path, "rocm.txt", "torch")
    versions['rocm'] = rocm_torch if rocm_torch else "[tbd]"

    # TPU
    tpu_torch = parse_requirements_file(repo_path, "tpu.txt", "torch")
    if not tpu_torch:
        # TPU might not have torch in requirements if it's a plugin
        versions['tpu'] = "[TPU]"
    else:
        versions['tpu'] = tpu_torch

    return versions


def extract_common_packages(repo_path: Path) -> Dict[str, str]:
    """Extract versions for common packages from requirements/common.txt."""
    packages = {}
    common_pkgs = ['transformers', 'tokenizers', 'compressed-tensors']

    for pkg in common_pkgs:
        version = parse_requirements_file(repo_path, "common.txt", pkg)
        packages[pkg] = version if version else "[tbd]"

    return packages


def extract_flash_attn_version(repo_path: Path) -> str:
    """Extract flash_attn version from Dockerfile.rocm_base."""
    fa_branch = parse_dockerfile_arg(repo_path, "Dockerfile.rocm_base", "FA_BRANCH")
    if fa_branch:
        # Return short form (8 chars) if it's a git hash
        if re.match(r'^[0-9a-f]+$', fa_branch):
            return fa_branch[:8]
        return fa_branch
    return "[tbd]"


def extract_nccl_version(repo_path: Path) -> str:
    """Extract nccl version from requirements/test.txt."""
    # NCCL is installed as nvidia-nccl-cu12 package
    nccl = parse_requirements_file(repo_path, "test.txt", "nvidia-nccl-cu12")
    return nccl if nccl else "[tbd]"


def extract_accelerator_packages(repo_path: Path) -> Dict[str, str]:
    """Extract versions for accelerator-specific packages."""
    packages = {}

    # flashinfer from cuda.txt
    flashinfer = parse_requirements_file(repo_path, "cuda.txt", "flashinfer-python")
    if not flashinfer:
        flashinfer = parse_requirements_file(repo_path, "cuda.txt", "flashinfer")
    packages['flashinfer'] = flashinfer if flashinfer else "[tbd]"

    # triton - check multiple sources
    triton = parse_requirements_file(repo_path, "rocm-build.txt", "triton")
    if not triton:
        triton = parse_requirements_file(repo_path, "test.txt", "triton")
    packages['triton'] = triton if triton else "[tbd]"

    # tpu-info from tpu.txt
    tpu_info = parse_requirements_file(repo_path, "tpu.txt", "tpu_info")
    if not tpu_info:
        tpu_info = parse_requirements_file(repo_path, "tpu.txt", "tpu-info")
    packages['tpu-info'] = tpu_info if tpu_info else "[TPU]"

    return packages


def extract_ep_kernel_versions(repo_path: Path) -> Dict[str, str]:
    """Extract EP kernel component versions from install script."""
    versions = {}
    script_path = "tools/ep_kernels/install_python_libraries.sh"

    # PPLX kernels
    pplx = parse_script_var(repo_path, script_path, "PPLX_COMMIT_HASH")
    versions['pplx-kernels'] = pplx[:8] if pplx and len(pplx) >= 8 else (pplx if pplx else "[tbd]")

    # DeepEP
    deepep = parse_script_var(repo_path, script_path, "DEEPEP_COMMIT_HASH")
    versions['deep-ep'] = deepep[:8] if deepep and len(deepep) >= 8 else (deepep if deepep else "[tbd]")

    # NVSHMEM
    nvshmem = parse_script_var(repo_path, script_path, "NVSHMEM_VER")
    versions['nvshmem'] = nvshmem if nvshmem else "[tbd]"

    return versions


def extract_deepgemm_version(repo_path: Path) -> str:
    """Extract DeepGEMM git hash from install script."""
    deepgemm = parse_script_var(repo_path, "tools/install_deepgemm.sh", "DEEPGEMM_GIT_REF")
    if deepgemm:
        # Return short form (8 chars) if it's a git hash
        if re.match(r'^[0-9a-f]+$', deepgemm) and len(deepgemm) >= 8:
            return deepgemm[:8]
        return deepgemm
    return "[tbd]"


def extract_nixl_version(repo_path: Path) -> str:
    """Extract nixl version from requirements files."""
    # Check tpu.txt first
    nixl = parse_requirements_file(repo_path, "tpu.txt", "nixl")
    if nixl:
        return nixl

    # Check kv_connectors.txt
    nixl = parse_requirements_file(repo_path, "kv_connectors.txt", "nixl")
    if nixl:
        return nixl

    return "[tbd]"


def extract_all_versions(repo_path: Path) -> List[Tuple[int, str, str]]:
    """
    Extract all component versions and return list of (row_num, component_name, version).
    Maintains exact spreadsheet order from row 16-43 with blank lines for merged cells.
    """
    versions = []

    # Row 16: python
    python_ver = safe_extract(extract_python_version, repo_path)
    versions.append((16, "python", python_ver))

    # Row 17: RHEL
    versions.append((17, "RHEL", "[tbd]"))

    # Row 18: gcc [specific to Spyre]
    gcc_ver = safe_extract(extract_gcc_version, repo_path)
    versions.append((18, "gcc [specific to Spyre]", gcc_ver))

    # Row 19: CUDA
    cuda_ver = safe_extract(extract_cuda_version, repo_path)
    versions.append((19, "CUDA", cuda_ver))

    # Row 20: ROCM
    rocm_ver = safe_extract(extract_rocm_version, repo_path)
    versions.append((20, "ROCM", rocm_ver))

    # Rows 21-23: Spyre plugins
    versions.append((21, "Spyre x86 plugin", "[Spyre]"))
    versions.append((22, "Spyre s390x plugin", "[Spyre]"))
    versions.append((23, "Spyre ppc64le plugin", "[Spyre]"))

    # Row 24: Merged cell (blank line)
    versions.append((24, "[merged cells]", ""))

    # Rows 25-28: torch variants
    torch_vers = safe_extract(extract_torch_versions, repo_path, default={})
    versions.append((25, "torch [CUDA]", torch_vers.get('cuda', '[tbd]')))
    versions.append((26, "torch [ROCM]", torch_vers.get('rocm', '[tbd]')))
    versions.append((27, "torch [TPU]", torch_vers.get('tpu', '[TPU]')))
    versions.append((28, "torch [Spyre]", "[Spyre]"))

    # Row 29: Merged cell (blank line)
    versions.append((29, "[merged cells]", ""))

    # Row 30: aiter [ROCM]
    aiter_ver = safe_extract(extract_aiter_version, repo_path)
    versions.append((30, "aiter [ROCM]", aiter_ver))

    # Common packages
    common_pkgs = safe_extract(extract_common_packages, repo_path, default={})

    # Row 31: compressed-tensors
    versions.append((31, "compressed-tensors [CUDA, ROCM, TPU, Spyre]",
                    common_pkgs.get('compressed-tensors', '[tbd]')))

    # Accelerator-specific packages
    accel_pkgs = safe_extract(extract_accelerator_packages, repo_path, default={})

    # Row 32: flashinfer [CUDA]
    versions.append((32, "flashinfer [CUDA]", accel_pkgs.get('flashinfer', '[tbd]')))

    # Row 33: flash_attn [ROCM]
    flash_attn_ver = safe_extract(extract_flash_attn_version, repo_path)
    versions.append((33, "flash_attn [ROCM]", flash_attn_ver))

    # Row 34: nccl
    nccl_ver = safe_extract(extract_nccl_version, repo_path)
    versions.append((34, "nccl", nccl_ver))

    # EP kernel versions
    ep_vers = safe_extract(extract_ep_kernel_versions, repo_path, default={})

    # Row 35: nvshmem
    versions.append((35, "nvshmem", ep_vers.get('nvshmem', '[tbd]')))

    # Rows 36-37: tokenizers
    versions.append((36, "tokenizers [CUDA, ROCM, TPU from 3.2.1]",
                    common_pkgs.get('tokenizers', '[tbd]')))
    versions.append((37, "tokenizers [Spyre]", "[Spyre]"))

    # Row 38: tpu-info [TPU]
    versions.append((38, "tpu-info [TPU]", accel_pkgs.get('tpu-info', '[TPU]')))

    # Rows 39-40: transformers
    versions.append((39, "transformers [CUDA, ROCM, TPU from 3.2.1]",
                    common_pkgs.get('transformers', '[tbd]')))
    versions.append((40, "transformers [Spyre]", "[Spyre]"))

    # Rows 41-42: triton
    versions.append((41, "triton [CUDA, ROCM,TPU from 3.2.1]",
                    accel_pkgs.get('triton', '[tbd]')))
    versions.append((42, "triton [Spyre]", "[Spyre]"))

    # Row 43: vllm-tgis-adapter (last row needed)
    versions.append((43, "vllm-tgis-adapter [CUDA, ROCM, Spyre]", "[tbd]"))

    # Note: Rows 44+ (llm-d dependencies and Spyre-specific dependencies) are not needed
    # for the spreadsheet copy-paste workflow

    return versions


def format_output(versions: List[Tuple[int, str, str]], show_labels: bool = False,
                 output_format: str = "simple") -> str:
    """
    Format versions for copy-paste to spreadsheet.

    Args:
        versions: List of (row_num, component_name, version) tuples
        show_labels: Show component names alongside values
        output_format: "simple", "validation", or "csv"
    """
    # Sort by row number
    sorted_versions = sorted(versions, key=lambda x: x[0])

    if output_format == "validation":
        lines = []
        lines.append("=" * 80)
        lines.append("Component Version Extraction Report")
        lines.append("=" * 80)
        lines.append(f"{'Row':<5} {'Component':<45} {'Version':<20} {'Status':<10}")
        lines.append("-" * 80)

        for row, name, version in sorted_versions:
            # Skip merged cells in the report
            if name == "[merged cells]":
                continue
            status = "✓" if version not in ['[tbd]', '[Spyre]', '[TPU]', ''] else "⚠"
            lines.append(f"{row:<5} {name:<45} {version:<20} {status:<10}")

        lines.append("=" * 80)

        # Summary statistics (excluding merged cells)
        components_only = [(r, n, v) for r, n, v in sorted_versions if n != "[merged cells]"]
        total = len(components_only)
        determined = sum(1 for _, _, v in components_only if v not in ['[tbd]', '[Spyre]', '[TPU]', ''])
        spyre = sum(1 for _, _, v in components_only if v == '[Spyre]')
        tpu = sum(1 for _, _, v in components_only if v == '[TPU]')
        tbd = sum(1 for _, _, v in components_only if v == '[tbd]')

        lines.append(f"Total components: {total}")
        lines.append(f"Determined: {determined}")
        lines.append(f"Spyre plugins: {spyre}")
        lines.append(f"TPU plugins: {tpu}")
        lines.append(f"TBD: {tbd}")
        lines.append("=" * 80)

        return '\n'.join(lines)

    elif output_format == "csv":
        lines = []
        for row, name, version in sorted_versions:
            if name == "[merged cells]":
                lines.append("")  # Blank line for merged cells
            else:
                lines.append(f"{row},{name},{version}")
        return '\n'.join(lines)

    else:  # simple
        lines = []
        for row, name, version in sorted_versions:
            if name == "[merged cells]":
                lines.append("")  # Blank line for merged cells
            elif show_labels:
                lines.append(f"{name}: {version}")
            else:
                lines.append(version)
        return '\n'.join(lines)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Extract component versions from vLLM repository for RHAI spreadsheet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ref v0.12.0
  %(prog)s --ref v0.11.2 --show-labels
  %(prog)s --ref main --output validation
  %(prog)s --ref v0.12.0 --repo-url https://github.com/vllm-project/vllm.git

Output can be copy-pasted directly into the spreadsheet column for the specified release.
        """
    )

    parser.add_argument(
        "--ref",
        type=str,
        required=True,
        help="vLLM git tag/ref to extract versions from (e.g., v0.12.0, main)"
    )

    parser.add_argument(
        "--repo-url",
        type=str,
        default="https://github.com/vllm-project/vllm.git",
        help="vLLM repository URL (default: https://github.com/vllm-project/vllm.git)"
    )

    parser.add_argument(
        "--show-labels",
        action="store_true",
        help="Show component names alongside values (for verification)"
    )

    parser.add_argument(
        "--output",
        choices=["simple", "validation", "csv"],
        default="simple",
        help="Output format: simple (column only), validation (with markers), csv (comma-separated)"
    )

    args = parser.parse_args()

    # Clone repo in temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Clone and checkout
            repo_path = clone_vllm_repo(temp_path, args.repo_url, args.ref)

            # Extract versions
            print(f"Extracting component versions from {args.ref}...", file=sys.stderr)
            versions = extract_all_versions(repo_path)

            # Format and print output
            output = format_output(versions, args.show_labels, args.output)
            print(output)

        except subprocess.CalledProcessError as e:
            print(f"Error: Git operation failed: {e}", file=sys.stderr)
            print(f"stderr: {e.stderr.decode() if e.stderr else 'N/A'}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
