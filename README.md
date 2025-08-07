# vLLM Dependencies Auto-filer

This tool automatically generates JIRA tickets for vLLM package updates by parsing diff files and creating properly formatted ticket requests.

## Overview

The tool helps automate the process of creating JIRA tickets for package updates in the vLLM project. It:

1. Parses a diff file to identify package changes
2. Generates structured ticket data for each package
3. Creates JIRA CLI commands to submit tickets
4. Provides preview and dry-run capabilities

## Files

- `parse_diff.py` - Parses the vLLM requirements diff and generates ticket files
- `jira_generator.py` - Generates JIRA CLI commands and provides preview functionality
- `vllm-reqs.diff` - The diff file showing package changes between vLLM versions
- `example-ticket.txt` - Template for JIRA ticket format
- `ticket_text/` - Directory containing generated ticket YAML files
- `requirements.txt` - Python dependencies

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install and configure JIRA CLI:
   ```bash
   # Install jira CLI (see https://github.com/ankitpokhrel/jira-cli)
   # Then configure it
   jira init
   ```

3. Ensure JIRA CLI is working:
   ```bash
   jira --version
   ```

## Usage

### Step 1: Parse the diff file

Parse the vLLM requirements diff to extract package changes:

```bash
python3 parse_diff.py
```

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

### Step 3: Generate JIRA commands

#### Option A: Generate a shell script (Recommended)

Generate a shell script with all JIRA commands:

```bash
python3 jira_generator.py --generate-script
```

This creates `create_jira_tickets.sh` that you can review and execute.

#### Option B: Interactive mode

Run in interactive mode (dry-run by default):

```bash
python3 jira_generator.py
```

Run for real (actually execute JIRA commands):

```bash
python3 jira_generator.py --no-dry-run
```

### Command Line Options

For `jira_generator.py`:

- `--preview-only` - Only show preview, don't process tickets
- `--package NAME` - Process only specific package
- `--generate-script` - Generate shell script instead of running commands
- `--script-output FILE` - Output file for generated script (default: create_jira_tickets.sh)
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

3. **Generate script:**
   ```bash
   python3 jira_generator.py --generate-script
   ```

4. **Review and execute script:**
   ```bash
   # Review the generated script
   less create_jira_tickets.sh
   
   # Execute it
   ./create_jira_tickets.sh
   ```

## Ticket Structure

Each generated ticket includes:

- **Epic Title:** `builder: <packagename> package update request`
- **Package Information:** Name, old version, new version
- **Files:** Which requirement files are affected
- **Context:** About vLLM v0.10.1 release
- **License:** Standard compatibility statement

## JIRA Configuration

Tickets are created with:
- **Project:** AIPCC
- **Assignee:** rh-ee-raravind
- **Components:** Accelerator Enablement, Application Platform
- **Label:** package
- **Priority:** Normal

## Notes

- The tickets are pre-emptive of the vLLM v0.10.1 release
- There may be further changes when v0.10.1 is officially cut
- All packages are needed for upstream compatibility in downstream releases
- Default mode is dry-run for safety - use `--no-dry-run` to actually execute

## JIRA CLI Command Format

The tool generates native JIRA CLI commands:

```bash
jira epic create \
  -p AIPCC \
  -n "builder: packagename package update request" \
  -s "builder: packagename package update request" \
  -b "ticket body..." \
  --no-input
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

## Doug notes...

automatically files jira deps, dude.

# stuff I did...

Create a JIRA API PAT by going to your profile and then making a personal access token. Save it in your .env file here.

```
source .env
docker run -it --rm \
  -v $PWD/.jira-cli:/root/.config/.jira:Z \
  -e JIRA_API_TOKEN=$JIRA_API_TOKEN \
  ghcr.io/ankitpokhrel/jira-cli:latest
```

First time through, do `jira init` and add your URL and username.

It should save in the local `.jira-cli` dir here.

My initial diff is from: 4da8bf20d08f1f8f97a4839d580eb923d0ca9415