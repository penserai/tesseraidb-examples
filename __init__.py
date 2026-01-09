"""
DTaaS Digital Twin Examples

This package contains comprehensive sample digital twins across various domains:

- smart_building: Smart office building with HVAC, sensors, access control
- manufacturing: Industry 4.0 factory with CNC machines, robots, QC equipment
- healthcare: Hospital with medical equipment and patient monitoring
- supply_chain: Global logistics with warehouses, trucks, and ships
- smart_city: Urban infrastructure, transit, and utilities
- robotics: Automated fulfillment center with AMRs and robotic arms
- energy_grid: Power grid with renewables and distribution
- automotive: Fleet management with EVs and telematics
- agriculture: Precision farming with sensors, drones, and tractors
- aerospace: Satellite constellation with ground stations

Usage:
    # Run individual examples
    python -m examples.smart_building.seed

    # Or run all examples
    python -m examples.seed_all
"""

__version__ = "1.0.0"

AVAILABLE_DOMAINS = [
    "smart_building",
    "manufacturing",
    "healthcare",
    "supply_chain",
    "smart_city",
    "robotics",
    "energy_grid",
    "automotive",
    "agriculture",
    "aerospace",
]
