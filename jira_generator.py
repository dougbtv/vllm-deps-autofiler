#!/usr/bin/env python3
"""
Generate JIRA CLI commands for creating package update tickets.
Provides preview functionality and dry-run mode.
"""

import yaml
import os
import subprocess
import time
import argparse
from pathlib import Path
from typing import List, Dict
import argparse

class JiraTicketGenerator:
    def __init__(self, ticket_dir: str, dry_run: bool = True):
        self.ticket_dir = Path(ticket_dir)
        self.dry_run = dry_run
        self.template_epic = "AIPCC-1"  # Template epic to clone from
    
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
        print("\n" + "="*80)
        print("📋 JIRA TICKET PREVIEW")
        print("="*80)
        
        print(f"{'Package':<25} {'Old Version':<15} {'New Version':<15} {'Change Type':<12} {'Files'}")
        print("-" * 80)
        
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
            
            print(f"{ticket['package_name']:<25} {old_ver:<15} {new_ver:<15} {change_type:<12} {files}")
        
        print(f"\nTotal tickets to create: {len(tickets)}")
        print("="*80)
    
    def preview_ticket_details(self, ticket: Dict):
        """Show detailed preview of a single ticket."""
        pkg_name = ticket['package_name']
        title = f"builder: {pkg_name} package update request"
        
        print(f"\n{'='*60}")
        print(f"📦 {pkg_name.upper()} TICKET DETAILS")
        print(f"{'='*60}")
        print(f"Epic Title: {title}")
        print(f"Package: {pkg_name}")
        print(f"Old Version: {ticket['old_version'] or 'N/A'}")
        print(f"New Version: {ticket['new_version'] or 'N/A'}")
        print(f"Files: {', '.join(ticket['files'])}")
        print(f"Template Epic: {self.template_epic}")
        
        print(f"\n{'='*60}")
        print("📝 TICKET BODY (PREVIEW)")
        print(f"{'='*60}")
        
        # Body preview (truncated)
        body_lines = ticket['body_description'].split('\n')
        preview_body = '\n'.join(body_lines[:15])
        if len(body_lines) > 15:
            preview_body += "\n... (truncated)"
        
        print(preview_body)
        print(f"{'='*60}")
    
    def create_jira_ticket(self, ticket: Dict) -> str:
        """Create a JIRA ticket using rhjira tool."""
        pkg_name = ticket['package_name']
        epic_name = f"builder: {pkg_name} package update request"
        description = ticket['body_description']
        
        if self.dry_run:
            print(f"🔍 [DRY RUN] Would clone {self.template_epic} and create epic for {pkg_name}")
            print(f"    Epic Name: {epic_name}")
            print(f"    Description: {description[:100]}...")
            return "FAKE-123"  # Return fake ID for dry run
        
        try:
            # Step 1: Clone the template epic
            print(f"🔄 Cloning {self.template_epic} for {pkg_name}...")
            clone_result = subprocess.run(
                ["rhjira", "clone", self.template_epic],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract the new epic ID from the output
            # Expected format: "Successfully created: https://issues.redhat.com/browse/AIPCC-XXXX"
            epic_url = None
            for line in clone_result.stdout.split('\n'):
                if "Successfully created:" in line:
                    epic_url = line.split(": ")[-1].strip()
                    break
            
            if not epic_url:
                raise Exception(f"Could not extract epic URL from clone output: {clone_result.stdout}")
            
            epic_id = epic_url.split("/")[-1]
            print(f"✅ Created new epic: {epic_id}")
            
            # Step 2: Update the epic with our details
            print(f"📝 Updating epic {epic_id} with package details...")
            edit_result = subprocess.run([
                "rhjira", "edit", epic_id,
                "--epicname", epic_name,
                "--summary", epic_name,
                "--description", description,
                "--noeditor"
            ], capture_output=True, text=True, check=True)
            
            print(f"✅ Successfully updated epic: {epic_id}")
            print(f"🔗 URL: {epic_url}")
            
            return epic_id
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating ticket for {pkg_name}: {e}")
            print(f"   Command: {' '.join(e.cmd)}")
            print(f"   Output: {e.stdout}")
            print(f"   Error: {e.stderr}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error creating ticket for {pkg_name}: {e}")
            return None


    
    def run_tickets(self, tickets: List[Dict], interactive: bool = True):
        """Run JIRA ticket creation directly using rhjira."""
        if self.dry_run:
            print("🔍 DRY RUN MODE - No actual tickets will be created\n")
        
        print(f"\n{'='*60}")
        print(f"{'JIRA TICKET CREATION':^60}")
        print(f"{'='*60}")
        print(f"Template Epic: {self.template_epic}")
        print(f"Total Tickets: {len(tickets)}")
        print(f"{'='*60}\n")
        
        created_tickets = []
        failed_tickets = []
        
        for i, ticket in enumerate(tickets, 1):
            pkg_name = ticket['package_name']
            print(f"\n📦 Processing {pkg_name} ({i}/{len(tickets)})")
            
            if interactive:
                self.preview_ticket_details(ticket)
                
                response = input("\nCreate this ticket? [Y/n]: ")
                if response.lower().startswith('n'):
                    print(f"⏭️  Skipped {pkg_name}")
                    continue
            
            epic_id = self.create_jira_ticket(ticket)
            
            if epic_id:
                created_tickets.append({
                    'package': pkg_name,
                    'epic_id': epic_id
                })
                print(f"✅ Successfully created {epic_id} for {pkg_name}")
            else:
                failed_tickets.append(pkg_name)
                print(f"❌ Failed to create ticket for {pkg_name}")
            
            # Add a small delay between requests to be nice to the server
            if not self.dry_run and i < len(tickets):
                time.sleep(1)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"{'EXECUTION SUMMARY':^60}")
        print(f"{'='*60}")
        print(f"✅ Successfully created: {len(created_tickets)} tickets")
        print(f"❌ Failed to create: {len(failed_tickets)} tickets")
        
        if created_tickets:
            print(f"\n📋 Created Tickets:")
            for ticket in created_tickets:
                print(f"   • {ticket['package']}: {ticket['epic_id']}")
        
        if failed_tickets:
            print(f"\n❌ Failed Tickets:")
            for pkg in failed_tickets:
                print(f"   • {pkg}")
        
        print(f"{'='*60}\n")
    
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
            print(f"❌ Package '{args.package}' not found!")
            return
    
    if not tickets:
        print("❌ No tickets found!")
        return
    
    generator.preview_tickets(tickets)
    
    if args.preview_only:
        return
    
    if not args.non_interactive:
        response = input(f"\nProceed with {len(tickets)} tickets? [Y/n]: ")
        if response.lower().startswith('n'):
            print("❌ Cancelled")
            return
    
    generator.run_tickets(tickets, interactive=not args.non_interactive)

if __name__ == "__main__":
    main()
