# vLLM Dependencies Auto-filer

This tool automatically generates JIRA tickets for vLLM package updates by parsing diff files and creating properly formatted ticket requests.

## Overview

The tool helps automate the process of creating JIRA tickets for package updates in the vLLM project. It:

1. Generates diffs between vLLM versions OR parses existing diff files
2. Filters requirements to focus on production dependencies (excludes test*, nightly*, cpu*)
3. Extracts package changes and generates structured ticket data
4. Creates JIRA tickets directly using [rhjira](https://gitlab.com/prarit/rhjira) tool with template epic cloning
5. Provides preview and dry-run capabilities

## Files

- `parse_diff.py` - Generates diffs from git and parses requirements changes to create ticket files
- `jira_generator.py` - Creates JIRA tickets directly using `rhjira` tool and provides preview functionality
- `generate_component_versions.py` - Extracts component versions from vLLM releases for RHAI spreadsheet
- `vllm-reqs.diff` - Example diff file showing package changes between vLLM versions
- `ticket_text/` - Directory containing generated ticket YAML files
- `requirements.txt` - Python dependencies

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install and configure rhjira tool:
   ```bash
   # Install rhjira (Red Hat JIRA CLI tool)
   pip install rhjira
   export JIRA_TOKEN=ZzzExampleHere
   ```

3. Ensure rhjira is working:
   ```bash
   rhjira --version
   rhjira dump AIPCC-1
   ```

## Usage

### Step 1: Generate or Parse Diff

#### Option A: Generate diff from vLLM repository (Recommended)

Generate a diff between two vLLM versions automatically:

```bash
# Compare v0.10.0 to main branch
python3 parse_diff.py --generate-diff --old-ref v0.10.0 --new-ref main

# Compare specific versions
python3 parse_diff.py --generate-diff --old-ref v0.9.0 --new-ref v0.10.0

# Use different output directory
python3 parse_diff.py --generate-diff --old-ref v0.10.0 --new-ref main --output-dir my_tickets

# Include package removals (excluded by default)
python3 parse_diff.py --generate-diff --old-ref v0.10.0 --new-ref main --include-removals
```

This will:
- Clone the vLLM repository to a temporary directory
- Extract requirements for both versions
- Filter out test*, nightly*, and cpu* requirements (keeping common, build, cuda, rocm, tpu)
- Generate a diff and save it for reference
- Parse the diff and create ticket files

#### Option B: Parse existing diff file

If you already have a diff file:

```bash
python3 parse_diff.py --diff-file your-diff-file.diff
```

### Supported Requirements Files

The tool automatically filters requirements to focus on production dependencies:

**Included:**
- `requirements/common.txt` and `requirements/common.in`
- `requirements/build.txt` and `requirements/build.in`
- `requirements/cuda.txt` and `requirements/cuda.in`
- `requirements/rocm.txt` and `requirements/rocm.in`
- `requirements/tpu.txt` and `requirements/tpu.in`

**Excluded:**
- `requirements/test*.txt` and `requirements/test*.in`
- `requirements/nightly*.txt` and `requirements/nightly*.in`
- `requirements/cpu*.txt` and `requirements/cpu*.in`

This will:
- Read `vllm-reqs.diff`
- Extract package changes (additions, updates, removals)
- Generate YAML files in `ticket_text/` directory for each package

### Step 2: Preview tickets

Preview what tickets will be created:

```bash
python3 jira_generator.py --preview-only
```

Preview a specific package:

```bash
python3 jira_generator.py --package transformers --preview-only
```

### Step 3: Create JIRA tickets

Run in dry-run mode to preview what will be created (default):

```bash
python3 jira_generator.py
```

Run for real (actually create JIRA tickets):

```bash
python3 jira_generator.py --no-dry-run
```

Run non-interactively (no prompts):

```bash
python3 jira_generator.py --no-dry-run --non-interactive
```

Process only a specific package:

```bash
python3 jira_generator.py --package transformers --no-dry-run
```

### Command Line Options

For `parse_diff.py`:

- `--diff-file FILE` - Path to existing diff file to parse
- `--generate-diff` - Generate diff from git repository
- `--old-ref REF` - Old git ref/tag/branch to compare from (default: v0.10.0)
- `--new-ref REF` - New git ref/tag/branch to compare to (default: main)
- `--repo-url URL` - vLLM repository URL
- `--output-dir DIR` - Directory to output ticket files (default: ticket_text)
- `--include-removals` - Include package removals in the output (default: exclude removals)

For `jira_generator.py`:

- `--preview-only` - Only show preview, don't process tickets
- `--package NAME` - Process only specific package
- `--no-dry-run` - Actually execute JIRA commands (default is dry-run)
- `--non-interactive` - Run without prompts
- `--ticket-dir DIR` - Directory containing ticket YAML files (default: ticket_text)

## Example Workflow

1. **Parse diff file:**
   ```bash
   python3 parse_diff.py
   ```

2. **Preview tickets:**
   ```bash
   python3 jira_generator.py --preview-only
   ```

3. **Create JIRA tickets:**
   ```bash
   # Dry run first to see what would be created
   python3 jira_generator.py
   
   # Actually create the tickets
   python3 jira_generator.py --no-dry-run
   ```

## Ticket Structure

Each generated ticket includes:

- **Epic Title:** `builder: <packagename> package update request`
- **Package Information:** Name, old version, new version
- **Files:** Which requirement files are affected
- **Context:** About vLLM v0.10.1 release
- **License:** Standard compatibility statement

## JIRA Configuration

Tickets are created by cloning the template epic **AIPCC-1** and then updating it with package-specific details. This approach ensures:

- Consistent epic structure and settings
- Proper project assignment and components
- Standardized workflow and labels

The tool uses the `rhjira` command-line tool to:
1. Clone the template epic: `rhjira clone AIPCC-1`
2. Update the cloned epic with package details: `rhjira edit <NEW_ID> --epicname "..." --description "..." --noeditor`

## rhjira Command Format

The tool uses rhjira commands to create tickets via template cloning:

```bash
# Step 1: Clone template epic
rhjira clone AIPCC-1

# Step 2: Update with package details
rhjira edit <NEW_EPIC_ID> \
  --epicname "builder: packagename package update request" \
  --summary "builder: packagename package update request" \
  --description "ticket body..." \
  --noeditor
```

## Sample Output

```
================================================================================
📋 JIRA TICKET PREVIEW
================================================================================
Package                   Old Version     New Version     Change Type  Files
--------------------------------------------------------------------------------
transformers              4.53.2          4.55.0          UPDATE       common.txt, test.in (+1 more)
openai                    1.87.0          1.98.0          UPDATE       common.txt
setproctitle              N/A             latest          NEW          common.txt, docs.txt
...

Total tickets to create: 20
================================================================================
```

## Setup Notes

### JIRA Authentication

You'll need to set up authentication for the rhjira tool. This typically involves:

1. Creating a JIRA API token from your profile
2. Configuring the rhjira tool with your credentials
3. Ensuring you have access to the AIPCC project and can clone AIPCC-1

### Template Epic

The tool relies on **AIPCC-1** as a template epic. This epic should have:
- Proper project assignment (AIPCC)
- Correct components and labels
- Appropriate workflow settings
- Standard epic structure

All new tickets are created by cloning this template and updating the content.

## Development Notes

My initial diff is from: 4da8bf20d08f1f8f97a4839d580eb923d0ca9415

---

# Component Version Mapper for RHAI Spreadsheet

## Overview

The `generate_component_versions.py` tool extracts component version information from a vLLM repository at a specific release tag and outputs it in a format suitable for the "RHAI Release to Component Version Mapping" spreadsheet.

This tool automates the tedious process of manually looking up versions for 35+ components across multiple files in the vLLM repository.

## Usage

### Basic Usage

Extract versions for vLLM v0.12.0 (simple column output for copy-paste):

```bash
python3 generate_component_versions.py --ref v0.12.0
```

This outputs version values one per line, ready to paste into the spreadsheet column.

### With Component Labels

Show component names alongside values for verification:

```bash
python3 generate_component_versions.py --ref v0.12.0 --show-labels
```

### Validation Report

Get a detailed report with statistics:

```bash
python3 generate_component_versions.py --ref v0.12.0 --output validation
```

### Additional Options

```bash
# Use different vLLM ref/tag
python3 generate_component_versions.py --ref v0.11.2

# Use different repository URL
python3 generate_component_versions.py --ref v0.12.0 --repo-url https://github.com/fork/vllm.git

# CSV format output
python3 generate_component_versions.py --ref v0.12.0 --output csv
```

## What It Extracts

The tool extracts versions for all components from row 16-54 in the spreadsheet:

- **System requirements**: Python, RHEL, GCC, CUDA, ROCM
- **PyTorch variants**: torch for CUDA, ROCM, TPU, Spyre
- **Common packages**: transformers, tokenizers, compressed-tensors
- **Accelerator-specific**: flashinfer, flash_attn, triton, tpu-info
- **System libraries**: nccl, nvshmem, aiter
- **LLM-D dependencies**: deep-ep, deep-gemm, nixl, pplx-kernels
- **Spyre-specific**: aiu-monitor, ibm-fms, ibm-sendnn, torch-sendnn

## Special Markers

- **[Spyre]**: Component is now a Spyre plugin (plugin architecture)
- **[TPU]**: Component is now a TPU plugin (plugin architecture)
- **[tbd]**: Value cannot be determined from vLLM repository (needs manual lookup)

## How It Works

The tool:

1. Clones the vLLM repository to a temporary directory
2. Checks out the specified tag/ref
3. Extracts versions from multiple sources:
   - `pyproject.toml` for Python version
   - `docker/Dockerfile` and `docker/Dockerfile.rocm_base` for system requirements
   - `requirements/*.txt` files for Python packages
   - `tools/*.sh` scripts for git-based dependencies
4. Maps extracted versions to spreadsheet rows
5. Formats output for easy copy-paste

## Example Output

**Simple mode** (default):
```
3.10
[tbd]
10
12.9.1
7.1
[Spyre]
...
```

**With labels** (--show-labels):
```
python: 3.10
RHEL: [tbd]
gcc [specific to Spyre]: 10
CUDA: 12.9.1
ROCM: 7.1
Spyre x86 plugin: [Spyre]
...
```

**Validation mode** (--output validation):
```
================================================================================
Component Version Extraction Report
================================================================================
Row   Component                                     Version              Status
--------------------------------------------------------------------------------
16    python                                        3.10                 ✓
17    RHEL                                          [tbd]                ⚠
18    gcc [specific to Spyre]                       10                   ✓
...
================================================================================
Total components: 35
Determined: 18
Spyre plugins: 11
TPU plugins: 1
TBD: 5
================================================================================
```

## Workflow

1. **Extract versions** for new vLLM release:
   ```bash
   python3 generate_component_versions.py --ref v0.12.0 --output validation
   ```

2. **Review** the validation report to see what was determined

3. **Copy values** for spreadsheet:
   ```bash
   python3 generate_component_versions.py --ref v0.12.0
   ```

4. **Paste** the output into the appropriate column in the spreadsheet

5. **Manually fill in** any `[tbd]` values that need to be determined from other sources