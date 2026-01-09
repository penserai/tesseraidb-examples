# Supply Chain Example

A comprehensive global supply chain digital twin demonstrating TesseraiDB's capabilities for logistics management, including warehouses, distribution centers, vehicles, shipments, and inventory tracking.

## Overview

- What this domain models: Global distribution network spanning North America, Europe, and Asia Pacific with 2.5 million annual shipments
- Key entities and relationships: Supply chain network, suppliers, warehouses, distribution centers, trucks, ships, containers, shipments, products, inventory, customers
- Real-world use cases: Real-time shipment tracking, inventory optimization, route optimization, demand forecasting, supplier performance, carbon footprint tracking

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

- **SupplyChainNetwork**: Top-level network entity
- **Supplier**: Global suppliers (China, Germany, Japan, Mexico, USA)
- **DistributionCenter**: Major distribution hubs
- **RegionalWarehouse**: Regional storage facilities
- **FulfillmentCenter**: Order fulfillment locations
- **ImportHub**: International import facilities
- **WarehouseZone**: Receiving, bulk, pick, pack, ship, cold zones
- **SemiTruck**: Long-haul freight trucks
- **DeliveryVan**: Last-mile delivery vehicles
- **RefrigeratedTruck**: Temperature-controlled transport
- **ContainerShip**: Ocean freight vessels
- **DryContainer/ReeferContainer**: Shipping containers
- **Shipment**: Inbound, outbound, and transfer shipments
- **Product**: SKU master data
- **InventoryLevel**: Stock levels per location
- **GPSTracker**: Vehicle tracking devices
- **TemperatureSensor**: Cold chain monitoring
- **Customer**: End customers and distributors

## Ontology

The supply chain ontology defines:

- **Network hierarchy**: Network -> Warehouse -> Zone
- **Transportation**: Vehicle -> transportedBy -> Shipment
- **Inventory**: InventoryLevel -> forProduct, atWarehouse
- **Shipments**: Shipment -> originatesFrom, destinedFor
- **Supplier relationships**: Network -> hasSupplier -> Supplier

## Web Dashboard

The `web_ui.py` provides visualization of:

- Global network map with facility status
- Shipment tracking and status
- Inventory levels and alerts
- Vehicle fleet tracking
- Supplier performance metrics

Start the dashboard to monitor supply chain operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all shipments with status
shipments = client.sparql.query("""
    PREFIX supply: <http://tesserai.io/ontology/supply_chain#>
    SELECT ?shipment ?status ?origin ?dest WHERE {
        ?shipment a ?type .
        ?shipment supply:status ?status .
        ?shipment supply:origin ?origin .
        ?shipment supply:destination ?dest .
        FILTER (?type IN (supply:InboundShipment, supply:OutboundShipment))
    }
""")

# Check inventory levels
inventory = client.sparql.query("""
    PREFIX supply: <http://tesserai.io/ontology/supply_chain#>
    SELECT ?product ?warehouse ?qty ?reorder WHERE {
        ?inv a supply:InventoryLevel .
        ?inv supply:forProduct ?product .
        ?inv supply:atWarehouse ?warehouse .
        ?inv supply:quantity ?qty .
        ?inv supply:reorderPoint ?reorder .
        FILTER (?qty < ?reorder)
    }
""")

# Update vehicle location
client.twins.update("truck-001", properties={
    "currentLocation": {"lat": 41.88, "lng": -87.63},
    "status": "in_transit",
    "currentLoad": 18000
})

# Get container status
containers = client.sparql.query("""
    PREFIX supply: <http://tesserai.io/ontology/supply_chain#>
    SELECT ?container ?ship ?status WHERE {
        ?container a ?type .
        ?container supply:status ?status .
        OPTIONAL { ?container supply:loadedOn ?ship }
        FILTER (?type IN (supply:DryContainer, supply:ReeferContainer))
    }
""")
```

## Additional Features

### Global Network

| Facility | Location | Type | Area |
|----------|----------|------|------|
| Los Angeles DC | USA | Distribution Center | 50,000 m2 |
| Chicago Warehouse | USA | Regional Warehouse | 75,000 m2 |
| Newark Hub | USA | Distribution Center | 60,000 m2 |
| Dallas Warehouse | USA | Regional Warehouse | 45,000 m2 |
| Rotterdam Hub | Netherlands | Distribution Center | 80,000 m2 |
| Frankfurt FC | Germany | Fulfillment Center | 35,000 m2 |
| Shanghai Hub | China | Import Hub | 100,000 m2 |
| Singapore Hub | Singapore | Distribution Center | 55,000 m2 |

### Fleet

- 7 Semi-trucks (22,000 kg capacity)
- 2 Delivery vans (2,000 kg capacity)
- 1 Refrigerated truck (18,000 kg)
- 3 Container ships (6,000-10,000 TEU)

### Suppliers

| Supplier | Country | Category |
|----------|---------|----------|
| Shanghai Electronics | China | Electronics |
| Shenzhen Components | China | Components |
| Munich Precision | Germany | Machinery |
| Tokyo Tech Industries | Japan | Electronics |
| Monterrey Manufacturing | Mexico | Assembly |
| Detroit Parts | USA | Automotive |

### Products & Inventory

- 5 product SKUs tracked
- Inventory at 7 warehouse locations
- Real-time stock level monitoring
- Automatic reorder point alerts

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
