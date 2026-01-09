#!/usr/bin/env python3
"""
Cascading Failure Analysis - ASCII Dependency Visualization
============================================================

Generates ASCII-based visualizations of infrastructure dependencies:
- Dependency tree view
- Layer-based architecture diagram
- Impact graph visualization

Usage:
    python visualize.py [--base-url URL]
    python visualize.py --tree COMPONENT      # Show dependency tree
    python visualize.py --layers              # Show layer diagram
    python visualize.py --impact COMPONENT    # Show impact graph
"""

import sys
import os
import argparse
from typing import Dict, List, Set, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


class Colors:
    """ANSI color codes."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


class InfrastructureVisualizer:
    """ASCII visualization of infrastructure dependencies."""

    LAYER_ORDER = [
        "PowerPlant", "Substation",
        "PowerFeed", "BackupGenerator", "UPSSystem",
        "ChillerPlant", "CoolingUnit",
        "NetworkSwitch",
        "ServerRack",
        "Application",
        "ControlSystem", "ProductionLine", "ManufacturingEquipment",
        "Warehouse", "Supplier", "LogisticsProvider",
    ]

    TYPE_ICONS = {
        "PowerPlant": "[PWR]",
        "Substation": "[SUB]",
        "PowerFeed": "[FED]",
        "BackupGenerator": "[GEN]",
        "UPSSystem": "[UPS]",
        "ChillerPlant": "[CHL]",
        "CoolingUnit": "[COL]",
        "NetworkSwitch": "[NET]",
        "ServerRack": "[SRV]",
        "Application": "[APP]",
        "ControlSystem": "[CTL]",
        "ProductionLine": "[PRD]",
        "ManufacturingEquipment": "[EQP]",
        "Warehouse": "[WHS]",
        "Supplier": "[SUP]",
        "LogisticsProvider": "[LOG]",
    }

    def __init__(self, client):
        self.client = client
        self.components: Dict[str, Dict] = {}
        self.forward_deps: Dict[str, List[str]] = defaultdict(list)
        self.reverse_deps: Dict[str, List[str]] = defaultdict(list)

    def load_infrastructure(self):
        """Load infrastructure data."""
        try:
            twins = self.client.twins.list(domain="cascading_failure")

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                component_id = twin_dict["id"]

                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                self.components[component_id] = {
                    "id": component_id,
                    "name": twin_dict.get("name", component_id),
                    "type": type_val.split("#")[-1] if type_val else "",
                    "properties": twin_dict.get("properties", {}),
                }

                for rel in twin_dict.get("relationships", []):
                    target = rel.get("target", "")
                    if target:
                        self.forward_deps[component_id].append(target)
                        self.reverse_deps[target].append(component_id)

            logger.info(f"Loaded {len(self.components)} components")

        except Exception as e:
            logger.error(f"Failed to load infrastructure: {e}")
            raise

    def get_icon(self, component_id: str) -> str:
        """Get icon for component type."""
        comp = self.components.get(component_id, {})
        comp_type = comp.get("type", "Unknown")
        return self.TYPE_ICONS.get(comp_type, "[???]")

    def get_color(self, component_id: str) -> str:
        """Get color based on component criticality."""
        comp = self.components.get(component_id, {})
        criticality = comp.get("properties", {}).get("criticality", "medium")

        colors = {
            "critical": Colors.RED,
            "high": Colors.YELLOW,
            "medium": Colors.CYAN,
            "low": Colors.GREEN,
        }
        return colors.get(criticality, Colors.RESET)

    def print_tree(self, root_id: str, max_depth: int = 5):
        """Print dependency tree from a root component."""
        if root_id not in self.components:
            print(f"Component {root_id} not found")
            return

        print("\n" + "=" * 70)
        print(f" DEPENDENCY TREE: {self.components[root_id]['name']}")
        print("=" * 70)
        print("\n Legend: [PWR]=Power, [SUB]=Substation, [UPS]=UPS,")
        print("         [NET]=Network, [SRV]=Server, [APP]=Application\n")

        visited: Set[str] = set()

        def print_node(comp_id: str, depth: int, prefix: str, is_last: bool):
            if depth > max_depth or comp_id in visited:
                if comp_id in visited:
                    print(f"{prefix}{'└── ' if is_last else '├── '}... (circular ref)")
                return

            visited.add(comp_id)

            comp = self.components.get(comp_id, {})
            icon = self.get_icon(comp_id)
            color = self.get_color(comp_id)
            name = comp.get("name", comp_id)[:30]

            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}{color}{icon} {name}{Colors.RESET}")

            # Get downstream dependencies
            deps = self.forward_deps.get(comp_id, [])

            new_prefix = prefix + ("    " if is_last else "│   ")

            for i, dep_id in enumerate(deps):
                if dep_id in self.components:
                    print_node(dep_id, depth + 1, new_prefix, i == len(deps) - 1)

        comp = self.components[root_id]
        icon = self.get_icon(root_id)
        color = self.get_color(root_id)
        print(f"{color}{icon} {comp['name']}{Colors.RESET}")

        deps = self.forward_deps.get(root_id, [])
        for i, dep_id in enumerate(deps):
            if dep_id in self.components:
                print_node(dep_id, 1, "", i == len(deps) - 1)

    def print_layers(self):
        """Print layer-based infrastructure diagram."""
        print("\n" + "=" * 80)
        print(" INFRASTRUCTURE LAYER DIAGRAM")
        print("=" * 80)

        # Group components by type
        by_type: Dict[str, List[str]] = defaultdict(list)
        for comp_id, comp in self.components.items():
            by_type[comp.get("type", "Unknown")].append(comp_id)

        # Define layers
        layers = [
            ("POWER GENERATION", ["PowerPlant"]),
            ("TRANSMISSION", ["Substation"]),
            ("DATA CENTER POWER", ["PowerFeed", "UPSSystem", "BackupGenerator"]),
            ("COOLING", ["ChillerPlant", "CoolingUnit"]),
            ("NETWORK", ["NetworkSwitch"]),
            ("COMPUTE", ["ServerRack"]),
            ("APPLICATIONS", ["Application"]),
            ("MANUFACTURING", ["ControlSystem", "ProductionLine", "ManufacturingEquipment"]),
            ("SUPPLY CHAIN", ["Warehouse", "Supplier", "LogisticsProvider"]),
        ]

        for layer_name, comp_types in layers:
            components = []
            for ct in comp_types:
                components.extend(by_type.get(ct, []))

            if not components:
                continue

            print(f"\n{Colors.BOLD}{'─' * 80}")
            print(f" {layer_name}")
            print(f"{'─' * 80}{Colors.RESET}")

            # Print components in rows of 3
            row = []
            for comp_id in components:
                comp = self.components[comp_id]
                icon = self.get_icon(comp_id)
                color = self.get_color(comp_id)
                name = comp_id[:18]
                row.append(f"{color}{icon} {name}{Colors.RESET}")

                if len(row) == 3:
                    print(" " + "  |  ".join(row))
                    row = []

            if row:
                print(" " + "  |  ".join(row))

            # Show connections to next layer
            if layer_name != "SUPPLY CHAIN":
                print(f"{Colors.DIM}         │         │         │{Colors.RESET}")
                print(f"{Colors.DIM}         ▼         ▼         ▼{Colors.RESET}")

    def print_impact_graph(self, source_id: str, max_nodes: int = 20):
        """Print impact graph showing cascade from a source."""
        if source_id not in self.components:
            print(f"Component {source_id} not found")
            return

        print("\n" + "=" * 70)
        print(f" IMPACT GRAPH: {self.components[source_id]['name']}")
        print("=" * 70)

        # BFS to find affected components
        affected = []
        visited = {source_id}
        queue = [(source_id, 0)]

        while queue and len(affected) < max_nodes:
            current, depth = queue.pop(0)
            if current != source_id:
                affected.append((current, depth))

            for dep_id in self.forward_deps.get(current, []):
                if dep_id not in visited and dep_id in self.components:
                    visited.add(dep_id)
                    queue.append((dep_id, depth + 1))

        # Group by depth
        by_depth: Dict[int, List[str]] = defaultdict(list)
        for comp_id, depth in affected:
            by_depth[depth].append(comp_id)

        # Print source
        comp = self.components[source_id]
        icon = self.get_icon(source_id)
        print(f"\n{Colors.RED}{Colors.BOLD}  ╔═══════════════════════════════════════╗")
        print(f"  ║  {icon} {comp['name'][:32]:<32} ║")
        print(f"  ║        >>> FAILURE SOURCE <<<         ║")
        print(f"  ╚═══════════════════════════════════════╝{Colors.RESET}")

        # Print cascade levels
        for depth in sorted(by_depth.keys()):
            components = by_depth[depth]

            print(f"\n{Colors.BOLD}  Level {depth} ({len(components)} affected):{Colors.RESET}")
            print(f"  {'─' * 50}")

            for comp_id in components[:8]:
                comp = self.components[comp_id]
                icon = self.get_icon(comp_id)
                color = self.get_color(comp_id)
                print(f"    {color}{icon} {comp['name'][:40]}{Colors.RESET}")

            if len(components) > 8:
                print(f"    ... and {len(components) - 8} more")

        # Summary
        total = len(affected)
        print(f"\n{Colors.YELLOW}  Total Impact: {total} components affected{Colors.RESET}")

    def print_mini_graph(self, component_id: str):
        """Print a mini ASCII graph of a component's immediate neighbors."""
        if component_id not in self.components:
            print(f"Component {component_id} not found")
            return

        upstream = self.reverse_deps.get(component_id, [])
        downstream = self.forward_deps.get(component_id, [])

        comp = self.components[component_id]
        icon = self.get_icon(component_id)
        color = self.get_color(component_id)

        print("\n" + "─" * 60)
        print(f" DEPENDENCY MAP: {comp['name']}")
        print("─" * 60)

        # Upstream
        if upstream:
            print("\n  DEPENDS ON:")
            for up_id in upstream[:5]:
                if up_id in self.components:
                    up_comp = self.components[up_id]
                    up_icon = self.get_icon(up_id)
                    up_color = self.get_color(up_id)
                    print(f"    {up_color}{up_icon} {up_comp['name'][:35]}{Colors.RESET}")
                    print(f"           │")
            print(f"           ▼")

        # Current
        print(f"\n  {color}{Colors.BOLD}╔══════════════════════════════════════╗")
        print(f"  ║  {icon} {comp['name'][:32]:<32} ║")
        print(f"  ╚══════════════════════════════════════╝{Colors.RESET}")

        # Downstream
        if downstream:
            print(f"           │")
            print(f"           ▼")
            print("  PROVIDES TO:")
            for down_id in downstream[:5]:
                if down_id in self.components:
                    down_comp = self.components[down_id]
                    down_icon = self.get_icon(down_id)
                    down_color = self.get_color(down_id)
                    print(f"    {down_color}{down_icon} {down_comp['name'][:35]}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(description="Infrastructure Visualization")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--tree", help="Show dependency tree from component")
    parser.add_argument("--layers", action="store_true",
                       help="Show layer-based diagram")
    parser.add_argument("--impact", help="Show impact graph from component")
    parser.add_argument("--map", help="Show mini dependency map for component")
    parser.add_argument("--list", action="store_true",
                       help="List all components")
    args = parser.parse_args()

    client = get_client(args.base_url)
    viz = InfrastructureVisualizer(client)

    print("Loading infrastructure...")
    viz.load_infrastructure()

    if not viz.components:
        print("No components found. Run seed.py first.")
        return

    if args.list:
        print("\nComponents:")
        for comp_id in sorted(viz.components.keys()):
            comp = viz.components[comp_id]
            icon = viz.get_icon(comp_id)
            print(f"  {icon} {comp_id}")
        return

    if args.tree:
        viz.print_tree(args.tree)
    elif args.layers:
        viz.print_layers()
    elif args.impact:
        viz.print_impact_graph(args.impact)
    elif args.map:
        viz.print_mini_graph(args.map)
    else:
        # Default: show layer diagram
        viz.print_layers()


if __name__ == "__main__":
    main()
