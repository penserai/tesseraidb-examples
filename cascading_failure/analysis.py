#!/usr/bin/env python3
"""
Cascading Failure Analysis - Vulnerability & Impact Analysis
=============================================================

Advanced analytics for infrastructure vulnerability assessment:
- Single Point of Failure (SPOF) detection
- Critical path analysis
- Blast radius estimation
- Risk scoring and prioritization
- What-if scenario modeling
- Mitigation recommendations

Usage:
    python analysis.py [--base-url URL] [--spof]           # Find single points of failure
    python analysis.py --blast-radius COMPONENT            # Estimate impact
    python analysis.py --critical-paths                    # Identify critical paths
    python analysis.py --vulnerability-report              # Full vulnerability report
"""

import sys
import os
import argparse
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger, NAMESPACE_PREFIXES


@dataclass
class VulnerabilityScore:
    """Vulnerability assessment for a component."""
    component_id: str
    component_name: str
    component_type: str
    is_spof: bool
    blast_radius: int
    downstream_critical: int
    criticality: str
    business_impact: float
    risk_score: float
    mitigation_priority: int
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CriticalPath:
    """A critical dependency path through the infrastructure."""
    path: List[str]
    total_business_impact: float
    weakest_link: str
    weakest_link_reliability: float
    path_reliability: float


class VulnerabilityAnalyzer:
    """
    Infrastructure vulnerability analysis engine.
    """

    def __init__(self, client):
        self.client = client
        self.components: Dict[str, Dict] = {}
        self.forward_deps: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.reverse_deps: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    def _normalize_properties(self, properties: Dict) -> Dict:
        """
        Normalize property names by stripping domain prefixes.
        The API returns properties like 'cascading_failure#redundancyLevel'
        but we want to access them as 'redundancyLevel'.
        """
        normalized = {}
        for key, value in properties.items():
            if '#' in key:
                short_key = key.split('#', 1)[1]
            else:
                short_key = key
            normalized[short_key] = value
        return normalized

    def _normalize_rel_type(self, rel_type: str) -> str:
        """Normalize relationship type by stripping domain prefixes."""
        # Handle both 'domain#rel/type' and 'domain#type' formats
        if '#' in rel_type:
            rel_type = rel_type.split('#', 1)[1]
        if rel_type.startswith('rel/'):
            rel_type = rel_type[4:]
        return rel_type

    def load_infrastructure(self):
        """Load all components and build dependency graph."""
        try:
            twins = self.client.twins.list(domain="cascading_failure")

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                component_id = twin_dict["id"]

                # Normalize properties (strip domain prefixes)
                raw_props = twin_dict.get("properties", {})
                normalized_props = self._normalize_properties(raw_props)

                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                self.components[component_id] = {
                    "id": component_id,
                    "name": twin_dict.get("name", component_id),
                    "type": type_val.split("#")[-1] if type_val else "",
                    "properties": normalized_props,
                }

            logger.info(f"Loaded {len(self.components)} components")

            # Load relationships separately for each component
            print("Loading infrastructure graph...")
            for component_id in self.components:
                try:
                    relationships = self.client.twins.get_relationships(component_id)
                    for rel in relationships:
                        rel_type = self._normalize_rel_type(rel.get("type", ""))
                        # Relationships use 'twin' field for the other end
                        other_twin = rel.get("twin", rel.get("target", ""))
                        direction = rel.get("direction", "outgoing")

                        if other_twin and other_twin in self.components:
                            if direction == "outgoing":
                                # This component -> other_twin
                                self.forward_deps[component_id].append((other_twin, rel_type))
                                self.reverse_deps[other_twin].append((component_id, rel_type))
                            else:
                                # other_twin -> this component (incoming)
                                self.forward_deps[other_twin].append((component_id, rel_type))
                                self.reverse_deps[component_id].append((other_twin, rel_type))
                except Exception as e:
                    logger.debug(f"No relationships for {component_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to load infrastructure: {e}")
            raise

    def calculate_blast_radius(self, component_id: str) -> Tuple[int, List[str]]:
        """
        Calculate how many components would be affected if this one fails.
        Uses BFS to traverse reverse dependencies (components that depend on this one).
        """
        if component_id not in self.components:
            return 0, []

        affected = set()
        queue = [component_id]
        affected_list = []

        while queue:
            current = queue.pop(0)

            # Traverse reverse_deps - components that depend on the current one
            for dependent, dep_type in self.reverse_deps.get(current, []):
                if dependent not in affected and dependent in self.components:
                    affected.add(dependent)
                    affected_list.append(dependent)
                    queue.append(dependent)

        return len(affected), affected_list

    def count_downstream_critical(self, component_id: str) -> int:
        """Count critical components in the downstream dependency chain."""
        blast_radius, affected = self.calculate_blast_radius(component_id)

        critical_count = 0
        for comp_id in affected:
            comp = self.components.get(comp_id, {})
            if comp.get("properties", {}).get("criticality") == "critical":
                critical_count += 1

        return critical_count

    def is_single_point_of_failure(self, component_id: str) -> bool:
        """
        Determine if a component is a single point of failure.
        A SPOF is a component with no redundancy that critical systems depend on.
        """
        comp = self.components.get(component_id, {})
        props = comp.get("properties", {})

        # Check if it has redundancy
        redundancy = props.get("redundancyLevel") or props.get("redundancy")
        has_redundancy = redundancy in ["N+1", "2N", "2N+1"]

        # Check if it has redundant paths
        has_redundant_path = props.get("hasRedundantPath", False)

        if has_redundancy or has_redundant_path:
            return False

        # Check if critical components depend on it
        downstream_critical = self.count_downstream_critical(component_id)
        return downstream_critical > 0

    def calculate_risk_score(self, component_id: str) -> float:
        """
        Calculate risk score based on:
        - Blast radius
        - Criticality of downstream systems
        - Component reliability
        - Business impact
        """
        comp = self.components.get(component_id, {})
        props = comp.get("properties", {})

        blast_radius, _ = self.calculate_blast_radius(component_id)
        downstream_critical = self.count_downstream_critical(component_id)

        # Factors
        reliability = props.get("reliability", 0.99)
        failure_likelihood = (1 - reliability) * 100  # Scale to 0-100

        business_impact = props.get("businessImpact", 5)

        criticality_weights = {"critical": 3, "high": 2, "medium": 1, "low": 0.5}
        crit_weight = criticality_weights.get(props.get("criticality", "medium"), 1)

        # Combined risk score
        risk_score = (
            blast_radius * 2 +
            downstream_critical * 5 +
            failure_likelihood * 10 +
            business_impact * 3 +
            crit_weight * 10
        )

        return risk_score

    def generate_recommendations(self, component_id: str,
                                  score: VulnerabilityScore) -> List[str]:
        """Generate mitigation recommendations for a component."""
        recommendations = []
        comp = self.components.get(component_id, {})
        props = comp.get("properties", {})

        if score.is_spof:
            recommendations.append("CRITICAL: Add redundancy - this is a single point of failure")

        if score.blast_radius > 10:
            recommendations.append(f"High blast radius ({score.blast_radius}): Consider failover mechanisms")

        if score.downstream_critical > 3:
            recommendations.append(f"Protects {score.downstream_critical} critical systems: "
                                  "Implement enhanced monitoring")

        redundancy = props.get("redundancyLevel") or props.get("redundancy")
        if redundancy == "N":
            recommendations.append("Upgrade from N to N+1 redundancy")

        reliability = props.get("reliability", 0.99)
        if reliability < 0.99:
            recommendations.append(f"Reliability {reliability:.3f} below target: "
                                  "Schedule preventive maintenance")

        if not recommendations:
            recommendations.append("No immediate actions required")

        return recommendations

    def find_single_points_of_failure(self) -> List[VulnerabilityScore]:
        """Find all single points of failure in the infrastructure."""
        spofs = []

        for comp_id, comp in self.components.items():
            if self.is_single_point_of_failure(comp_id):
                blast_radius, _ = self.calculate_blast_radius(comp_id)
                downstream_critical = self.count_downstream_critical(comp_id)
                risk_score = self.calculate_risk_score(comp_id)
                props = comp.get("properties", {})

                score = VulnerabilityScore(
                    component_id=comp_id,
                    component_name=comp.get("name", comp_id),
                    component_type=comp.get("type", "Unknown"),
                    is_spof=True,
                    blast_radius=blast_radius,
                    downstream_critical=downstream_critical,
                    criticality=props.get("criticality", "medium"),
                    business_impact=props.get("businessImpact", 5),
                    risk_score=risk_score,
                    mitigation_priority=1 if risk_score > 50 else 2,
                )
                score.recommendations = self.generate_recommendations(comp_id, score)
                spofs.append(score)

        return sorted(spofs, key=lambda x: -x.risk_score)

    def find_critical_paths(self, max_paths: int = 10) -> List[CriticalPath]:
        """
        Find critical dependency paths - paths where failure would have
        maximum business impact.
        """
        # Find leaf nodes (applications, end systems)
        leaves = []
        for comp_id, comp in self.components.items():
            if comp.get("type") in ["Application", "ProductionLine", "ManufacturingEquipment"]:
                leaves.append(comp_id)

        critical_paths = []

        for leaf_id in leaves:
            # Trace back to root dependencies
            path = [leaf_id]
            current = leaf_id
            visited = {leaf_id}
            total_impact = self.components[leaf_id].get("properties", {}).get("businessImpact", 5)
            min_reliability = 1.0

            while True:
                # Find upstream dependencies
                upstream = self.reverse_deps.get(current, [])
                if not upstream:
                    break

                # Pick highest impact upstream
                best_upstream = None
                best_impact = 0

                for up_id, rel_type in upstream:
                    if up_id not in visited and up_id in self.components:
                        impact = self.components[up_id].get("properties", {}).get("businessImpact", 0)
                        if impact > best_impact:
                            best_impact = impact
                            best_upstream = up_id

                if not best_upstream:
                    break

                visited.add(best_upstream)
                path.insert(0, best_upstream)
                current = best_upstream
                total_impact += best_impact

                reliability = self.components[best_upstream].get("properties", {}).get("reliability", 0.99)
                if reliability < min_reliability:
                    min_reliability = reliability
                    weakest = best_upstream

            if len(path) > 2:
                # Calculate path reliability (product of individual reliabilities)
                path_reliability = 1.0
                for comp_id in path:
                    rel = self.components[comp_id].get("properties", {}).get("reliability", 0.99)
                    path_reliability *= rel

                critical_paths.append(CriticalPath(
                    path=path,
                    total_business_impact=total_impact,
                    weakest_link=weakest if 'weakest' in dir() else path[0],
                    weakest_link_reliability=min_reliability,
                    path_reliability=path_reliability,
                ))

        return sorted(critical_paths, key=lambda x: -x.total_business_impact)[:max_paths]

    def analyze_component(self, component_id: str) -> Optional[VulnerabilityScore]:
        """Perform full vulnerability analysis on a single component."""
        if component_id not in self.components:
            return None

        comp = self.components[component_id]
        props = comp.get("properties", {})

        blast_radius, _ = self.calculate_blast_radius(component_id)
        downstream_critical = self.count_downstream_critical(component_id)
        risk_score = self.calculate_risk_score(component_id)

        score = VulnerabilityScore(
            component_id=component_id,
            component_name=comp.get("name", component_id),
            component_type=comp.get("type", "Unknown"),
            is_spof=self.is_single_point_of_failure(component_id),
            blast_radius=blast_radius,
            downstream_critical=downstream_critical,
            criticality=props.get("criticality", "medium"),
            business_impact=props.get("businessImpact", 5),
            risk_score=risk_score,
            mitigation_priority=1 if risk_score > 50 else (2 if risk_score > 25 else 3),
        )
        score.recommendations = self.generate_recommendations(component_id, score)

        return score


def print_spof_report(spofs: List[VulnerabilityScore]):
    """Print single points of failure report."""
    print("\n" + "=" * 90)
    print(" SINGLE POINTS OF FAILURE ANALYSIS")
    print("=" * 90)

    if not spofs:
        print("\n No single points of failure detected!")
        print(" All critical systems have redundancy.")
        return

    print(f"\n Found {len(spofs)} Single Points of Failure:")
    print("-" * 90)
    print(f" {'Component':<30} {'Type':<18} {'Blast':<7} {'Crit':<6} {'Risk':>7}")
    print("-" * 90)

    for spof in spofs[:15]:
        print(f" {spof.component_id[:30]:<30} {spof.component_type[:18]:<18} "
              f"{spof.blast_radius:<7} {spof.downstream_critical:<6} "
              f"{spof.risk_score:>7.1f}")

    print("\n PRIORITY MITIGATIONS:")
    print("-" * 90)

    for spof in spofs[:5]:
        print(f"\n [{spof.mitigation_priority}] {spof.component_name}")
        for rec in spof.recommendations[:3]:
            print(f"    - {rec}")


def print_critical_paths_report(paths: List[CriticalPath]):
    """Print critical paths report."""
    print("\n" + "=" * 90)
    print(" CRITICAL DEPENDENCY PATHS")
    print("=" * 90)

    for i, path in enumerate(paths[:10], 1):
        print(f"\n Path {i}: Business Impact = {path.total_business_impact:.1f}")
        print(f" Path Reliability: {path.path_reliability:.4f}")
        print(f" Weakest Link: {path.weakest_link} ({path.weakest_link_reliability:.4f})")
        print(" Chain: " + " -> ".join(path.path))


def print_blast_radius_report(analyzer: VulnerabilityAnalyzer, component_id: str):
    """Print blast radius analysis for a component."""
    blast_radius, affected = analyzer.calculate_blast_radius(component_id)
    score = analyzer.analyze_component(component_id)

    if not score:
        print(f"Component {component_id} not found")
        return

    print("\n" + "=" * 80)
    print(f" BLAST RADIUS ANALYSIS: {score.component_name}")
    print("=" * 80)

    print(f"\n Component: {component_id}")
    print(f" Type: {score.component_type}")
    print(f" Criticality: {score.criticality}")
    print(f" Is SPOF: {'Yes' if score.is_spof else 'No'}")

    print(f"\n IMPACT METRICS:")
    print(f"   Blast Radius:        {blast_radius} components")
    print(f"   Critical Affected:   {score.downstream_critical}")
    print(f"   Business Impact:     {score.business_impact}")
    print(f"   Risk Score:          {score.risk_score:.1f}")

    print(f"\n AFFECTED COMPONENTS:")
    print("-" * 60)

    # Group by type
    by_type = defaultdict(list)
    for comp_id in affected:
        comp = analyzer.components.get(comp_id, {})
        by_type[comp.get("type", "Unknown")].append(comp_id)

    for comp_type, components in sorted(by_type.items()):
        print(f"\n {comp_type} ({len(components)}):")
        for comp_id in components[:5]:
            comp = analyzer.components.get(comp_id, {})
            print(f"   - {comp.get('name', comp_id)}")
        if len(components) > 5:
            print(f"   ... and {len(components) - 5} more")

    print(f"\n RECOMMENDATIONS:")
    for rec in score.recommendations:
        print(f"   - {rec}")


def print_vulnerability_report(analyzer: VulnerabilityAnalyzer):
    """Print comprehensive vulnerability report."""
    print("\n" + "=" * 90)
    print(" INFRASTRUCTURE VULNERABILITY REPORT")
    print("=" * 90)

    # Overall stats
    total = len(analyzer.components)
    print(f"\n Total Components: {total}")

    # Find SPOFs
    spofs = analyzer.find_single_points_of_failure()
    print(f" Single Points of Failure: {len(spofs)}")

    # Risk distribution
    high_risk = 0
    medium_risk = 0
    low_risk = 0

    for comp_id in analyzer.components:
        risk = analyzer.calculate_risk_score(comp_id)
        if risk > 50:
            high_risk += 1
        elif risk > 25:
            medium_risk += 1
        else:
            low_risk += 1

    print(f"\n RISK DISTRIBUTION:")
    print(f"   High Risk:   {high_risk} ({high_risk/total*100:.1f}%)")
    print(f"   Medium Risk: {medium_risk} ({medium_risk/total*100:.1f}%)")
    print(f"   Low Risk:    {low_risk} ({low_risk/total*100:.1f}%)")

    # Top vulnerabilities
    all_scores = []
    for comp_id in analyzer.components:
        score = analyzer.analyze_component(comp_id)
        if score:
            all_scores.append(score)

    all_scores.sort(key=lambda x: -x.risk_score)

    print("\n TOP 10 HIGHEST RISK COMPONENTS:")
    print("-" * 90)
    print(f" {'#':<3} {'Component':<30} {'Type':<18} {'SPOF':<5} "
          f"{'Blast':<6} {'Risk':>8}")
    print("-" * 90)

    for i, score in enumerate(all_scores[:10], 1):
        spof_str = "Yes" if score.is_spof else "No"
        print(f" {i:<3} {score.component_id[:30]:<30} "
              f"{score.component_type[:18]:<18} {spof_str:<5} "
              f"{score.blast_radius:<6} {score.risk_score:>8.1f}")

    # Critical paths
    paths = analyzer.find_critical_paths()
    if paths:
        print("\n CRITICAL DEPENDENCY PATHS:")
        print("-" * 90)
        for i, path in enumerate(paths[:3], 1):
            print(f" {i}. Impact={path.total_business_impact:.0f}, "
                  f"Reliability={path.path_reliability:.4f}")
            print(f"    {' -> '.join(p[:15] for p in path.path[:5])}")
            if len(path.path) > 5:
                print(f"    ... ({len(path.path) - 5} more hops)")


def main():
    parser = argparse.ArgumentParser(description="Cascading Failure Vulnerability Analysis")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--spof", action="store_true",
                       help="Find single points of failure")
    parser.add_argument("--blast-radius", help="Calculate blast radius for component")
    parser.add_argument("--critical-paths", action="store_true",
                       help="Find critical dependency paths")
    parser.add_argument("--vulnerability-report", action="store_true",
                       help="Generate full vulnerability report")
    parser.add_argument("--component", help="Analyze specific component")
    args = parser.parse_args()

    client = get_client(args.base_url)
    analyzer = VulnerabilityAnalyzer(client)

    print("Loading infrastructure graph...")
    analyzer.load_infrastructure()

    if not analyzer.components:
        print("No components found. Run seed.py first.")
        return

    if args.spof:
        spofs = analyzer.find_single_points_of_failure()
        print_spof_report(spofs)

    elif args.blast_radius:
        print_blast_radius_report(analyzer, args.blast_radius)

    elif args.critical_paths:
        paths = analyzer.find_critical_paths()
        print_critical_paths_report(paths)

    elif args.component:
        score = analyzer.analyze_component(args.component)
        if score:
            print(f"\n Component: {score.component_name}")
            print(f" Type: {score.component_type}")
            print(f" SPOF: {score.is_spof}")
            print(f" Blast Radius: {score.blast_radius}")
            print(f" Risk Score: {score.risk_score:.1f}")
            print(f" Recommendations:")
            for rec in score.recommendations:
                print(f"   - {rec}")
        else:
            print(f"Component {args.component} not found")

    else:
        # Default to vulnerability report
        print_vulnerability_report(analyzer)


if __name__ == "__main__":
    main()
