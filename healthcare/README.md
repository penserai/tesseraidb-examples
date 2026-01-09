# Healthcare Example

A comprehensive hospital digital twin demonstrating TesseraiDB's capabilities for medical equipment asset tracking, patient flow optimization, and resource management.

## Overview

- What this domain models: Level 1 Trauma Center with 650 beds, 24 operating rooms, and comprehensive medical services
- Key entities and relationships: Hospital, buildings, departments, patient rooms, medical imaging equipment, surgical robots, patient monitors, ventilators, laboratory equipment
- Real-world use cases: Medical equipment tracking, patient flow optimization, resource allocation, capacity planning, equipment utilization analytics, compliance tracking

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# (Optional) Start the web dashboard
python web_ui.py
```

## Digital Twins

List of main twin types created:

- **Hospital**: Top-level hospital entity
- **HospitalBuilding**: Main building, cancer center, cardiac pavilion, etc.
- **HospitalDepartment**: Emergency, ICU, NICU, surgery, cardiology, oncology
- **OperatingRoom**: General, cardiac, neuro, orthopedic, robotic surgery
- **PatientRoom**: ICU rooms with isolation capability
- **MRI/CT/X-Ray**: Medical imaging equipment
- **Ultrasound/PET-CT/Mammography**: Diagnostic imaging
- **PatientMonitor**: Bedside monitoring systems
- **Ventilator**: Mechanical ventilation equipment
- **InfusionPump**: IV medication delivery
- **DaVinciRobot/MAKORobot/ROSARobot**: Surgical robots
- **ChemistryAnalyzer/HematologyAnalyzer**: Laboratory equipment
- **PharmacyRobot/MedicationCabinet**: Pharmacy automation
- **Sterilizer**: Autoclave and ETO sterilization

## Ontology

The healthcare ontology defines:

- **Facility hierarchy**: Hospital -> Building -> Department -> Room
- **Equipment relationships**: Department -> hasEquipment -> Device
- **Location tracking**: Equipment -> locatedIn -> Room
- **Medical systems**: HVAC, medical gas, nurse call integration

## Web Dashboard

The `web_ui.py` provides visualization of:

- Equipment location and status
- Department capacity and utilization
- Operating room scheduling
- Equipment maintenance alerts
- Patient flow metrics

Start the dashboard to monitor hospital operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all medical imaging equipment
imaging = client.sparql.query("""
    PREFIX health: <http://tesserai.io/ontology/healthcare#>
    SELECT ?equip ?name ?type ?status WHERE {
        ?equip a ?type .
        ?equip health:name ?name .
        ?equip health:status ?status .
        FILTER (?type IN (health:MRI, health:CT, health:XRay, health:Ultrasound))
    }
""")

# Find equipment due for maintenance
maintenance = client.sparql.query("""
    PREFIX health: <http://tesserai.io/ontology/healthcare#>
    SELECT ?equip ?name ?nextMaint WHERE {
        ?equip health:name ?name .
        ?equip health:nextMaintenance ?nextMaint .
        FILTER (?nextMaint < "2026-06-01")
    }
""")

# Update equipment status
client.twins.update("mri-001", properties={
    "status": "in_use",
    "scansToday": 15,
    "currentPatient": "PT-12345"
})

# Get ICU room status
icu_rooms = client.sparql.query("""
    PREFIX health: <http://tesserai.io/ontology/healthcare#>
    SELECT ?room ?occupied WHERE {
        ?room a health:PatientRoom .
        ?room health:roomType "ICU" .
        ?room health:isOccupied ?occupied .
    }
""")
```

## Additional Features

### Medical Imaging Equipment

| Type | Count | Models |
|------|-------|--------|
| MRI | 2 | Siemens MAGNETOM Vida 3T, GE SIGNA Premier 3T |
| CT | 3 | Siemens SOMATOM Force, GE Revolution CT, Canon Aquilion ONE |
| X-Ray | 4 | Fixed and portable units |
| Ultrasound | 2 | GE Voluson E10, Philips EPIQ Elite |
| PET-CT | 1 | Siemens Biograph Vision Quadra |

### Surgical Capabilities

- 10 Operating rooms (general, cardiac, neuro, orthopedic, robotic, trauma)
- 2 da Vinci Xi surgical robots
- 1 MAKO robotic arm for orthopedics
- 1 ROSA neurosurgical robot

### ICU Capacity

- 20 ICU beds with full monitoring
- 8 ventilators
- 30 infusion pumps
- Negative pressure isolation rooms

### Laboratory Equipment

- Chemistry analyzer (Roche Cobas 8000)
- Hematology analyzer (Sysmex XN-9000)
- Blood gas analyzer
- Coagulation analyzer
- PCR system

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
