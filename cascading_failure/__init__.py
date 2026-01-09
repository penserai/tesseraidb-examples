"""
Cascading Failure Analysis Example for TesserAI DB

This example demonstrates sophisticated failure propagation analysis using
digital twin graphs, featuring:
- Complex dependency networks (power grid, IT infrastructure, supply chain)
- Failure propagation simulation with realistic delay models
- Impact analysis with business criticality assessment
- Automatic mitigation recommendations
- Graph-based vulnerability detection

This is a key differentiator from traditional graph databases like Neo4j
and Neptune - showing how semantic reasoning combined with graph structure
enables true cascading failure prediction.

Modules:
    seed.py - Creates interconnected infrastructure digital twins
    simulation.py - Failure propagation simulation engine
    analysis.py - Impact analysis and vulnerability detection
    visualize.py - ASCII-based dependency visualization
"""

__all__ = ["seed", "simulation", "analysis", "visualize"]
