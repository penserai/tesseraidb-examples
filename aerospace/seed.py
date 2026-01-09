#!/usr/bin/env python3
"""
Aerospace / Satellite Constellation Digital Twin Example

This example creates a comprehensive digital twin of a satellite constellation,
including satellites, ground stations, payloads, and mission control.

Domain: Aerospace / Space Systems
Use Cases:
  - Satellite health monitoring
  - Orbit prediction and collision avoidance
  - Ground station scheduling
  - Payload management
  - Anomaly detection
  - Mission planning
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Domain for this seed script
DOMAIN = "aerospace"
AERO_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_aerospace_twin(data: dict) -> dict:
    """Prepare a twin dict for the aerospace domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{AERO_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_aerospace():
    """Seed the aerospace/satellite digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # CONSTELLATION
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "constellation-globalnet",
        "type": "SatelliteConstellation",
        "name": "GlobalNet Communications Constellation",
        "description": "Low Earth Orbit communications satellite constellation",
        "properties": {
            "operator": "GlobalNet Space Systems",
            "purpose": "broadband_communications",
            "orbitType": "LEO",
            "totalSatellites": 150,
            "operationalSatellites": 142,
            "orbitalPlanes": 6,
            "satellitesPerPlane": 25,
            "altitude": 550,
            "altitudeUnit": "km",
            "inclination": 53,
            "inclinationUnit": "degrees",
            "coverageArea": "global",
            "launchProvider": "SpaceX",
            "missionStartDate": "2022-01-15"
        }
    }))

    # =========================================================================
    # SATELLITES
    # =========================================================================
    orbital_planes = [
        {"plane": 1, "raan": 0},
        {"plane": 2, "raan": 60},
        {"plane": 3, "raan": 120},
        {"plane": 4, "raan": 180},
        {"plane": 5, "raan": 240},
        {"plane": 6, "raan": 300},
    ]

    sat_id = 1
    for plane in orbital_planes:
        for i in range(25):
            satellite_id = f"sat-{sat_id:04d}"
            status = "operational" if sat_id <= 142 else ("standby" if sat_id <= 145 else "decommissioned")

            all_twins.append(prepare_aerospace_twin({
                "id": satellite_id,
                "type": "CommunicationsSatellite",
                "name": f"GlobalNet-{sat_id:04d}",
                "properties": {
                    "noradId": 50000 + sat_id,
                    "internationalDesignator": f"2022-{sat_id:03d}A",
                    "orbitalPlane": plane["plane"],
                    "slotInPlane": i + 1,
                    "altitude": 550 + (sat_id % 10) - 5,
                    "altitudeUnit": "km",
                    "inclination": 53.0,
                    "inclinationUnit": "degrees",
                    "raan": plane["raan"] + (i * 0.5),
                    "meanAnomaly": i * 14.4,
                    "eccentricity": 0.0001,
                    "orbitalPeriod": 95.5,
                    "periodUnit": "minutes",
                    "launchDate": f"2022-{(sat_id // 50) + 1:02d}-15",
                    "mass": 260,
                    "massUnit": "kg",
                    "power": 3200,
                    "powerUnit": "W",
                    "batteryLevel": 85 + (sat_id % 15),
                    "solarArrayStatus": "nominal",
                    "attitudeControl": "reaction_wheels",
                    "attitudeError": 0.05,
                    "attitudeErrorUnit": "degrees",
                    "thermalStatus": "nominal",
                    "temperature": 22,
                    "temperatureUnit": "Celsius",
                    "status": status
                }
            }))
            all_relationships.append(("constellation-globalnet", "hasSatellite", satellite_id, None))

            sat_id += 1

    # =========================================================================
    # PAYLOADS (Communication Transponders)
    # =========================================================================
    for sat_num in range(1, 143):  # Operational satellites only
        satellite_id = f"sat-{sat_num:04d}"

        # Ka-band payload
        ka_payload_id = f"payload-ka-{sat_num:04d}"
        all_twins.append(prepare_aerospace_twin({
            "id": ka_payload_id,
            "type": "KaBandPayload",
            "name": f"Ka-Band Transponder - {satellite_id}",
            "properties": {
                "band": "Ka",
                "frequencyRange": {"downlink": "17.7-20.2 GHz", "uplink": "27.5-30.0 GHz"},
                "bandwidth": 500,
                "bandwidthUnit": "MHz",
                "eirp": 52,
                "eirpUnit": "dBW",
                "beams": 16,
                "activeBeams": 14,
                "throughput": 20,
                "throughputUnit": "Gbps",
                "power": 800,
                "powerUnit": "W",
                "status": "active"
            }
        }))
        all_relationships.append((satellite_id, "hasPayload", ka_payload_id, None))

        # Ku-band payload
        ku_payload_id = f"payload-ku-{sat_num:04d}"
        all_twins.append(prepare_aerospace_twin({
            "id": ku_payload_id,
            "type": "KuBandPayload",
            "name": f"Ku-Band Transponder - {satellite_id}",
            "properties": {
                "band": "Ku",
                "frequencyRange": {"downlink": "10.7-12.7 GHz", "uplink": "14.0-14.5 GHz"},
                "bandwidth": 250,
                "bandwidthUnit": "MHz",
                "eirp": 48,
                "eirpUnit": "dBW",
                "beams": 8,
                "activeBeams": 7,
                "throughput": 8,
                "throughputUnit": "Gbps",
                "power": 400,
                "powerUnit": "W",
                "status": "active"
            }
        }))
        all_relationships.append((satellite_id, "hasPayload", ku_payload_id, None))

    # =========================================================================
    # GROUND STATIONS
    # =========================================================================
    ground_stations = [
        {"id": "gs-001", "name": "Svalbard Gateway", "lat": 78.2, "lng": 15.4, "country": "Norway", "type": "gateway"},
        {"id": "gs-002", "name": "Alaska Gateway", "lat": 64.8, "lng": -147.7, "country": "USA", "type": "gateway"},
        {"id": "gs-003", "name": "Hawaii Gateway", "lat": 21.3, "lng": -157.8, "country": "USA", "type": "gateway"},
        {"id": "gs-004", "name": "Santiago Gateway", "lat": -33.4, "lng": -70.6, "country": "Chile", "type": "gateway"},
        {"id": "gs-005", "name": "Perth Gateway", "lat": -31.9, "lng": 115.9, "country": "Australia", "type": "gateway"},
        {"id": "gs-006", "name": "Dubai Gateway", "lat": 25.2, "lng": 55.3, "country": "UAE", "type": "gateway"},
        {"id": "gs-007", "name": "London TT&C", "lat": 51.5, "lng": -0.1, "country": "UK", "type": "ttc"},
        {"id": "gs-008", "name": "Virginia TT&C", "lat": 38.9, "lng": -77.0, "country": "USA", "type": "ttc"},
        {"id": "gs-009", "name": "Singapore TT&C", "lat": 1.3, "lng": 103.8, "country": "Singapore", "type": "ttc"},
    ]

    for gs in ground_stations:
        all_twins.append(prepare_aerospace_twin({
            "id": gs["id"],
            "type": "GroundStation",
            "name": gs["name"],
            "properties": {
                "stationType": gs["type"],
                "coordinates": {"lat": gs["lat"], "lng": gs["lng"]},
                "country": gs["country"],
                "antennas": 4 if gs["type"] == "gateway" else 2,
                "antennaDiameter": 7.3 if gs["type"] == "gateway" else 13,
                "antennaDiameterUnit": "meters",
                "bands": ["Ka", "Ku"] if gs["type"] == "gateway" else ["S", "X"],
                "uplinkCapacity": 10 if gs["type"] == "gateway" else 0.1,
                "downlinkCapacity": 40 if gs["type"] == "gateway" else 0.5,
                "capacityUnit": "Gbps",
                "elevation": 500,
                "elevationUnit": "meters",
                "redundancy": True,
                "backupPower": "48 hours",
                "status": "operational"
            }
        }))
        all_relationships.append(("constellation-globalnet", "hasGroundStation", gs["id"], None))

    # =========================================================================
    # MISSION CONTROL CENTER
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "mcc-primary",
        "type": "MissionControlCenter",
        "name": "Primary Mission Control Center",
        "properties": {
            "location": "Hawthorne, California, USA",
            "coordinates": {"lat": 33.9, "lng": -118.3},
            "operators": 150,
            "redundancy": "hot_standby",
            "backupMCC": "mcc-backup",
            "capabilities": ["ttc", "orbit_determination", "collision_avoidance", "mission_planning"],
            "systemsMonitored": 150,
            "activeAlerts": 3,
            "status": "operational"
        }
    }))
    all_relationships.append(("constellation-globalnet", "controlledBy", "mcc-primary", None))

    # Backup MCC
    all_twins.append(prepare_aerospace_twin({
        "id": "mcc-backup",
        "type": "MissionControlCenter",
        "name": "Backup Mission Control Center",
        "properties": {
            "location": "Austin, Texas, USA",
            "coordinates": {"lat": 30.3, "lng": -97.7},
            "operators": 50,
            "redundancy": "warm_standby",
            "status": "standby"
        }
    }))

    # =========================================================================
    # ORBIT DETERMINATION SYSTEM
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "ods-001",
        "type": "OrbitDeterminationSystem",
        "name": "Orbit Determination System",
        "properties": {
            "vendor": "AGI",
            "software": "STK",
            "version": "12.5",
            "trackingSources": ["GPS", "ground_radar", "laser_ranging"],
            "accuracy": 10,
            "accuracyUnit": "meters",
            "updateFrequency": 15,
            "updateFrequencyUnit": "minutes",
            "conjunctionsTracked": 45,
            "status": "operational"
        }
    }))
    all_relationships.append(("mcc-primary", "uses", "ods-001", None))

    # =========================================================================
    # COLLISION AVOIDANCE SYSTEM
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "cas-001",
        "type": "CollisionAvoidanceSystem",
        "name": "Collision Avoidance System",
        "properties": {
            "vendor": "LeoLabs",
            "integrationWith": ["Space Surveillance Network", "18th Space Defense Squadron"],
            "warningThreshold": 1,
            "warningThresholdUnit": "km",
            "maneuverThreshold": 0.5,
            "activeWarnings": 2,
            "maneuversThisMonth": 5,
            "status": "operational"
        }
    }))
    all_relationships.append(("mcc-primary", "uses", "cas-001", None))

    # =========================================================================
    # SUBSYSTEMS (for sample satellites)
    # =========================================================================
    subsystem_types = [
        {"type": "ADCS", "name": "Attitude Determination & Control", "status": "nominal"},
        {"type": "EPS", "name": "Electrical Power System", "status": "nominal"},
        {"type": "TCS", "name": "Thermal Control System", "status": "nominal"},
        {"type": "OBC", "name": "On-Board Computer", "status": "nominal"},
        {"type": "COMM", "name": "Communications Subsystem", "status": "nominal"},
        {"type": "PROP", "name": "Propulsion System", "status": "nominal"},
    ]

    for sat_num in range(1, 11):  # Sample of 10 satellites
        satellite_id = f"sat-{sat_num:04d}"
        for subsys in subsystem_types:
            subsys_id = f"subsys-{subsys['type'].lower()}-{sat_num:04d}"
            all_twins.append(prepare_aerospace_twin({
                "id": subsys_id,
                "type": f"{subsys['type']}Subsystem",
                "name": f"{subsys['name']} - {satellite_id}",
                "properties": {
                    "subsystemType": subsys["type"],
                    "status": subsys["status"],
                    "healthScore": 95 + (sat_num % 5),
                    "temperature": 20 + (sat_num % 10),
                    "temperatureUnit": "Celsius",
                    "powerConsumption": 50 + (sat_num * 5),
                    "powerUnit": "W",
                    "lastTelemetry": "2024-12-15T10:00:00Z",
                    "anomalyCount": sat_num % 3
                }
            }))
            all_relationships.append((satellite_id, "hasSubsystem", subsys_id, None))

    # =========================================================================
    # LAUNCH VEHICLES
    # =========================================================================
    launches = [
        {"id": "launch-001", "name": "GlobalNet Launch 1", "vehicle": "Falcon 9", "date": "2022-01-15", "satellites": 25},
        {"id": "launch-002", "name": "GlobalNet Launch 2", "vehicle": "Falcon 9", "date": "2022-03-20", "satellites": 25},
        {"id": "launch-003", "name": "GlobalNet Launch 3", "vehicle": "Falcon 9", "date": "2022-06-10", "satellites": 25},
        {"id": "launch-004", "name": "GlobalNet Launch 4", "vehicle": "Falcon 9", "date": "2022-09-05", "satellites": 25},
        {"id": "launch-005", "name": "GlobalNet Launch 5", "vehicle": "Falcon 9", "date": "2022-12-01", "satellites": 25},
        {"id": "launch-006", "name": "GlobalNet Launch 6", "vehicle": "Falcon 9", "date": "2023-03-15", "satellites": 25},
    ]

    for launch in launches:
        all_twins.append(prepare_aerospace_twin({
            "id": launch["id"],
            "type": "Launch",
            "name": launch["name"],
            "properties": {
                "launchVehicle": launch["vehicle"],
                "launchDate": launch["date"],
                "launchSite": "Cape Canaveral SLC-40",
                "satellitesDeployed": launch["satellites"],
                "orbitAchieved": "LEO 550km",
                "missionStatus": "success",
                "boosterRecovery": True
            }
        }))
        all_relationships.append(("constellation-globalnet", "deployedBy", launch["id"], None))

    # =========================================================================
    # SPACE WEATHER MONITORING
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "space-weather-monitor",
        "type": "SpaceWeatherMonitor",
        "name": "Space Weather Monitoring System",
        "properties": {
            "dataSources": ["NOAA SWPC", "ESA Space Weather"],
            "solarFluxIndex": 120,
            "kpIndex": 3,
            "protonFlux": "nominal",
            "electronFlux": "nominal",
            "radiationStormLevel": "S0",
            "geomagneticStormLevel": "G0",
            "lastUpdate": "2024-12-15T10:00:00Z",
            "alerts": []
        }
    }))
    all_relationships.append(("mcc-primary", "monitors", "space-weather-monitor", None))

    # =========================================================================
    # USER TERMINALS (Sample)
    # =========================================================================
    terminal_types = [
        {"type": "Consumer", "count": 10},
        {"type": "Enterprise", "count": 5},
        {"type": "Maritime", "count": 3},
        {"type": "Aviation", "count": 2},
    ]

    terminal_id = 1
    for term_type in terminal_types:
        for i in range(term_type["count"]):
            tid = f"terminal-{terminal_id:05d}"
            all_twins.append(prepare_aerospace_twin({
                "id": tid,
                "type": f"{term_type['type']}Terminal",
                "name": f"{term_type['type']} Terminal {terminal_id:05d}",
                "properties": {
                    "terminalType": term_type["type"],
                    "manufacturer": "GlobalNet",
                    "model": f"{term_type['type']}Kit v2",
                    "coordinates": {"lat": 40.0 + (terminal_id * 0.5), "lng": -100.0 + (terminal_id * 0.3)},
                    "connectedSatellite": f"sat-{(terminal_id % 142) + 1:04d}",
                    "signalStrength": 85 + (terminal_id % 15),
                    "signalStrengthUnit": "dB",
                    "downloadSpeed": 150 + (terminal_id * 5),
                    "uploadSpeed": 20 + terminal_id,
                    "speedUnit": "Mbps",
                    "latency": 25 + (terminal_id % 10),
                    "latencyUnit": "ms",
                    "status": "connected",
                    "activeSince": "2024-06-15"
                }
            }))
            all_relationships.append((tid, "connectedTo", f"sat-{(terminal_id % 142) + 1:04d}", None))
            terminal_id += 1

    # =========================================================================
    # INTER-SATELLITE LINKS
    # =========================================================================
    # Create ISLs between adjacent satellites in each plane
    for plane_num, plane in enumerate(orbital_planes):
        base_sat = (plane_num * 25) + 1
        for i in range(24):  # 25 satellites, 24 links
            sat1 = f"sat-{base_sat + i:04d}"
            sat2 = f"sat-{base_sat + i + 1:04d}"
            isl_id = f"isl-{base_sat + i:04d}-{base_sat + i + 1:04d}"

            all_twins.append(prepare_aerospace_twin({
                "id": isl_id,
                "type": "InterSatelliteLink",
                "name": f"ISL {sat1} <-> {sat2}",
                "properties": {
                    "linkType": "optical",
                    "wavelength": 1550,
                    "wavelengthUnit": "nm",
                    "dataRate": 10,
                    "dataRateUnit": "Gbps",
                    "distance": 2000,
                    "distanceUnit": "km",
                    "latency": 6.7,
                    "latencyUnit": "ms",
                    "status": "active"
                }
            }))
            all_relationships.append((isl_id, "connects", sat1, None))
            all_relationships.append((isl_id, "connects", sat2, None))

    # =========================================================================
    # TELEMETRY SYSTEM
    # =========================================================================
    all_twins.append(prepare_aerospace_twin({
        "id": "telemetry-system",
        "type": "TelemetrySystem",
        "name": "Constellation Telemetry System",
        "properties": {
            "parameters_monitored": 15000,
            "samplingRate": 1,
            "samplingRateUnit": "Hz",
            "storageCapacity": 100,
            "storageCapacityUnit": "TB",
            "retentionPeriod": 365,
            "retentionPeriodUnit": "days",
            "anomalyDetection": True,
            "mlModels": ["thermal_anomaly", "power_degradation", "attitude_drift"],
            "status": "operational"
        }
    }))
    all_relationships.append(("mcc-primary", "operates", "telemetry-system", None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Aerospace / Satellite Constellation", twins_created, relationships_created)
    logger.info("Aerospace digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_aerospace()
