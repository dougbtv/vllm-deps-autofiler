#!/usr/bin/env python3
"""
Generate JIRA CLI commands for creating package update tickets.
Provides preview functionality and dry-run mode.
"""

import yaml
import os
import subprocess
from pathlib import Path
from typing import List, Dict
import argparse

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

class JiraTicketGenerator:
    def __init__(self, ticket_dir: str, dry_run: bool = True):
        self.ticket_dir = Path(ticket_dir)
        self.dry_run = dry_run
        self.assignee = "rh-ee-raravind"
        self.project = "AIPCC"
        self.components = ["Accelerator Enablement", "Application Platform"]
        self.label = "package"
    
    def load_ticket_files(self) -> List[Dict]:
        """Load all ticket YAML files."""
        tickets = []
        for yaml_file in self.ticket_dir.glob("*.yaml"):
            with open(yaml_file, 'r') as f:
                ticket_data = yaml.safe_load(f)
                ticket_data['filename'] = yaml_file.name
                tickets.append(ticket_data)
        return sorted(tickets, key=lambda x: x['package_name'])
    
    def preview_tickets(self, tickets: List[Dict]):
        """Display a preview of all tickets to be created."""
        console.print("\n[bold blue]📋 JIRA Ticket Preview[/bold blue]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Package", style="cyan", width=20)
        table.add_column("Old Version", style="yellow", width=15)
        table.add_column("New Version", style="green", width=15)
        table.add_column("Files", style="dim", width=30)
        table.add_column("Change Type", style="blue", width=12)
        
        for ticket in tickets:
            old_ver = ticket['old_version'] or "N/A"
            new_ver = ticket['new_version'] or "N/A"
            files = ", ".join(ticket['files'][:2])  # Show first 2 files
            if len(ticket['files']) > 2:
                files += f" (+{len(ticket['files'])-2} more)"
            
            # Determine change type
            if ticket['old_version'] is None:
                change_type = "NEW"
            elif ticket['new_version'] is None:
                change_type = "REMOVE"
            else:
                change_type = "UPDATE"
            
            table.add_row(
                ticket['package_name'],
                old_ver,
                new_ver,
                files,
                change_type
            )
        
        console.print(table)
        console.print(f"\n[bold]Total tickets to create: {len(tickets)}[/bold]")
    
    def preview_ticket_details(self, ticket: Dict):
        """Show detailed preview of a single ticket."""
        pkg_name = ticket['package_name']
        
        # Title
        title = f"builder: {pkg_name} package update request"
        
        console.print(Panel(
            f"[bold cyan]Epic Title:[/bold cyan] {title}\n"
            f"[bold cyan]Package:[/bold cyan] {pkg_name}\n"
            f"[bold cyan]Old Version:[/bold cyan] {ticket['old_version'] or 'N/A'}\n"
            f"[bold cyan]New Version:[/bold cyan] {ticket['new_version'] or 'N/A'}\n"
            f"[bold cyan]Files:[/bold cyan] {', '.join(ticket['files'])}\n"
            f"[bold cyan]Assignee:[/bold cyan] {self.assignee}\n"
            f"[bold cyan]Components:[/bold cyan] {', '.join(self.components)}\n"
            f"[bold cyan]Label:[/bold cyan] {self.label}",
            title=f"📦 {pkg_name} Ticket Details",
            border_style="green"
        ))
        
        # Body preview (truncated)
        body_lines = ticket['body_description'].split('\n')
        preview_body = '\n'.join(body_lines[:10])
        if len(body_lines) > 10:
            preview_body += "\n... (truncated)"
        
        console.print(Panel(
            preview_body,
            title="📝 Ticket Body (Preview)",
            border_style="yellow"
        ))
    
    def generate_jira_commands(self, ticket: Dict) -> List[str]:
        """Generate JIRA CLI commands for a single ticket."""
        pkg_name = ticket['package_name']
        title = f"builder: {pkg_name} package update request"
        body = ticket['body_description'].replace('"', '\\"').replace('\n', '\\n')
        
        commands = []
        
        # Create epic command
        create_cmd = [
            "docker", "run", "-it", "--rm",
            "-v", "$PWD/.jira-cli:/root/.config/.jira:Z",
            "-e", "JIRA_API_TOKEN=$JIRA_API_TOKEN",
            "ghcr.io/ankitpokhrel/jira-cli:latest",
            "jira", "epic", "create",
            "-p", self.project,
            "-n", f'"{title}"',
            "-s", f'"{title}"',
            "-b", f'"{body}"',
            "--no-input"
        ]
        commands.append(" ".join(create_cmd))
        
        # Edit command (placeholder - we'll need the epic ID from the create command)
        edit_cmd = [
            "docker", "run", "-it", "--rm",
            "-v", "$PWD/.jira-cli:/root/.config/.jira:Z", 
            "-e", "JIRA_API_TOKEN=$JIRA_API_TOKEN",
            "ghcr.io/ankitpokhrel/jira-cli:latest",
            "jira", "issue", "edit", "<EPIC_ID>",
            "-s", f'"{title}"',
            "-y", "Normal",
            "-a", self.assignee,
            "-l", self.label
        ]
        
        # Add components
        for component in self.components:
            edit_cmd.extend(["-C", f'"{component}"'])
        
        commands.append(" ".join(edit_cmd))
        
        return commands
    
    def run_tickets(self, tickets: List[Dict], interactive: bool = True):
        """Run JIRA commands for all tickets."""
        if self.dry_run:
            console.print("[bold yellow]🔍 DRY RUN MODE - Commands will be displayed but not executed[/bold yellow]\n")
        
        for i, ticket in enumerate(tickets, 1):
            pkg_name = ticket['package_name']
            console.print(f"\n[bold blue]📦 Processing {pkg_name} ({i}/{len(tickets)})[/bold blue]")
            
            if interactive:
                self.preview_ticket_details(ticket)
                
                if not console.input("\n[bold]Continue with this ticket? [Y/n]: ").lower().startswith('n'):
                    self.process_single_ticket(ticket)
                else:
                    console.print(f"[yellow]Skipped {pkg_name}[/yellow]")
            else:
                self.process_single_ticket(ticket)
    
    def process_single_ticket(self, ticket: Dict):
        """Process a single ticket."""
        pkg_name = ticket['package_name']
        commands = self.generate_jira_commands(ticket)
        
        console.print(f"\n[bold green]Commands for {pkg_name}:[/bold green]")
        
        for i, cmd in enumerate(commands, 1):
            console.print(f"\n[dim]Command {i}:[/dim]")
            console.print(Panel(cmd, border_style="dim"))
            
            if not self.dry_run:
                if console.input(f"Execute command {i}? [Y/n]: ").lower().startswith('n'):
                    console.print("[yellow]Command skipped[/yellow]")
                    continue
                
                # Execute the command
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        console.print(f"[green]✓ Command executed successfully[/green]")
                        console.print(result.stdout)
                    else:
                        console.print(f"[red]✗ Command failed[/red]")
                        console.print(result.stderr)
                except Exception as e:
                    console.print(f"[red]Error executing command: {e}[/red]")

def main():
    parser = argparse.ArgumentParser(description="Generate JIRA tickets for vLLM package updates")
    parser.add_argument("--ticket-dir", default="ticket_text", help="Directory containing ticket YAML files")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually execute JIRA commands")
    parser.add_argument("--non-interactive", action="store_true", help="Run without prompts")
    parser.add_argument("--preview-only", action="store_true", help="Only show preview, don't process tickets")
    parser.add_argument("--package", help="Process only specific package")
    
    args = parser.parse_args()
    
    generator = JiraTicketGenerator(
        ticket_dir=args.ticket_dir,
        dry_run=not args.no_dry_run
    )
    
    tickets = generator.load_ticket_files()
    
    if args.package:
        tickets = [t for t in tickets if t['package_name'] == args.package]
        if not tickets:
            console.print(f"[red]Package '{args.package}' not found![/red]")
            return
    
    if not tickets:
        console.print("[red]No tickets found![/red]")
        return
    
    generator.preview_tickets(tickets)
    
    if args.preview_only:
        return
    
    if not args.non_interactive:
        if console.input(f"\n[bold]Proceed with {len(tickets)} tickets? [Y/n]: ").lower().startswith('n'):
            console.print("[yellow]Cancelled[/yellow]")
            return
    
    generator.run_tickets(tickets, interactive=not args.non_interactive)

if __name__ == "__main__":
    main()
