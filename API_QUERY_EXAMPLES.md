# DTaaS Cross-Domain API Query Examples

After running `cross_domain_scenario.py`, you have a Smart Hospital with 48 digital twins across 5 domains. Here are interesting queries you can run.

**Note:** All examples use `Bearer example-token`. Adjust if you used a different token.

---

## 1. List All Twins

```bash
curl -s "http://localhost:8080/api/twins" \
  -H "Authorization: Bearer example-token" | jq '.total'
# Returns: 48
```

## 2. Filter by Domain

### Healthcare Domain
```bash
curl -s "http://localhost:8080/api/twins?domain=healthcare" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {id, name, type}'
```

### Robotics Domain
```bash
curl -s "http://localhost:8080/api/twins?domain=robotics" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {id, name, type}'
```

### Smart Building Domain
```bash
curl -s "http://localhost:8080/api/twins?domain=smart_building" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {id, name, type}'
```

### Supply Chain Domain
```bash
curl -s "http://localhost:8080/api/twins?domain=supply_chain" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {id, name, type}'
```

### Energy Grid Domain
```bash
curl -s "http://localhost:8080/api/twins?domain=energy_grid" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {id, name, type}'
```

---

## 3. Get Specific Twin Details

### Hospital Details
```bash
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:smart-hospital-central" \
  -H "Authorization: Bearer example-token" | jq .
```

### MRI Scanner Details
```bash
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:mri-001" \
  -H "Authorization: Bearer example-token" | jq .
```

---

## 4. Get Relationships (Cross-Domain Links)

The relationships endpoint now returns both **outgoing** and **incoming** relationships with direction info.

### Hospital's Relationships (outgoing)
```bash
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:smart-hospital-central/relationships" \
  -H "Authorization: Bearer example-token" | jq .
```

### Operating Room's Relationships (shows incoming HVAC, sensors, robots)
```bash
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:or-room-01/relationships" \
  -H "Authorization: Bearer example-token" | jq .
# Returns: HVAC maintains, sensors monitor, cleaning robot services, etc.
```

### Filter by Direction
```bash
# Only outgoing relationships
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:smart-hospital-central/relationships?direction=outgoing" \
  -H "Authorization: Bearer example-token" | jq .

# Only incoming relationships
curl -s "http://localhost:8080/api/twins/urn:tesserai:twin:or-room-01/relationships?direction=incoming" \
  -H "Authorization: Bearer example-token" | jq .
```

---

## 5. SPARQL Queries (Advanced)

SPARQL queries run on a specific twin's graph. Here are examples:

### Count All Triples in Hospital
```bash
curl -s -X POST "http://localhost:8080/twins/urn:tesserai:twin:smart-hospital-central/query" \
  -H "Authorization: Bearer example-token" \
  -H "Content-Type: application/sparql-query" \
  -d 'SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'
```

### Find All Properties of a Twin
```bash
curl -s -X POST "http://localhost:8080/twins/urn:tesserai:twin:mri-001/query" \
  -H "Authorization: Bearer example-token" \
  -H "Content-Type: application/sparql-query" \
  -d 'SELECT ?property ?value WHERE { ?s ?property ?value }'
```

---

## 6. Domain Statistics

### Count Twins per Domain
```bash
echo "=== Twins by Domain ==="
for domain in healthcare robotics smart_building supply_chain energy_grid; do
  count=$(curl -s "http://localhost:8080/api/twins?domain=$domain" \
    -H "Authorization: Bearer example-token" | jq '.total')
  echo "$domain: $count"
done
```

### Find All Robots
```bash
curl -s "http://localhost:8080/api/twins?domain=robotics" \
  -H "Authorization: Bearer example-token" | jq '.data[] | {name, type, properties}'
```

### Find All Sensors
```bash
curl -s "http://localhost:8080/api/twins?domain=smart_building" \
  -H "Authorization: Bearer example-token" | jq '.data[] | select(.type | contains("Sensor")) | {name, type}'
```

---

## 7. Cross-Domain Analysis Examples

### Find Energy Infrastructure Supporting Healthcare
```bash
curl -s "http://localhost:8080/api/twins?domain=energy_grid" \
  -H "Authorization: Bearer example-token" | \
  jq '.data[] | {name, type, capacity: .properties.capacity, unit: .properties.capacityUnit}'
```

### Find HVAC Systems (Smart Building serving Healthcare)
```bash
curl -s "http://localhost:8080/api/twins?domain=smart_building" \
  -H "Authorization: Bearer example-token" | \
  jq '.data[] | select(.type | contains("HVAC")) | {name, properties}'
```

### Find All Medical Devices
```bash
curl -s "http://localhost:8080/api/twins?domain=healthcare" \
  -H "Authorization: Bearer example-token" | \
  jq '.data[] | select(.type | test("MRI|CT|Ventilator|Surgical")) | {name, type}'
```

### Supply Chain Status
```bash
curl -s "http://localhost:8080/api/twins?domain=supply_chain" \
  -H "Authorization: Bearer example-token" | \
  jq '.data[] | {name, type, status: .properties.status, priority: .properties.priority}'
```

---

## 8. Validation Examples

### Create Twin with SHACL Validation
```bash
# This will FAIL validation (invalid data)
curl -s -X POST "http://localhost:8080/twins/test-invalid?schema=automotive" \
  -H "Authorization: Bearer example-token" \
  -H "Content-Type: text/turtle" \
  -d '@prefix auto: <http://tesserai.io/ontology/automotive#> .
@prefix dtaas: <http://tesserai.io/ontology/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://example.org/bad-car> a auto:Vehicle ;
  dtaas:name "Bad Car" ;
  auto:year "1800"^^xsd:integer .' | jq .
```

### Validate Existing Twin
```bash
curl -s -X POST "http://localhost:8080/twins/urn:tesserai:twin:mri-001/validate?schema=healthcare" \
  -H "Authorization: Bearer example-token" | jq .
```

---

## 9. Ontology Management

### List All Ontologies
```bash
curl -s "http://localhost:8080/ontologies" \
  -H "Authorization: Bearer example-token" | jq '.ontologies[] | .id'
```

### Get Ontology Content (Turtle format)
```bash
curl -s "http://localhost:8080/ontologies/healthcare" \
  -H "Authorization: Bearer example-token"
```

---

## 10. Quick Stats Script

Run this to get a full overview:

```bash
#!/bin/bash
TOKEN="example-token"
BASE="http://localhost:8080"

echo "=== DTaaS Cross-Domain Overview ==="
echo ""

# Total twins
total=$(curl -s "$BASE/api/twins" -H "Authorization: Bearer $TOKEN" | jq '.total')
echo "Total Twins: $total"
echo ""

# By domain
echo "Twins by Domain:"
for domain in healthcare robotics smart_building supply_chain energy_grid; do
  count=$(curl -s "$BASE/api/twins?domain=$domain" -H "Authorization: Bearer $TOKEN" | jq '.total')
  printf "  %-15s: %s\n" "$domain" "$count"
done
echo ""

# Ontologies
ont_count=$(curl -s "$BASE/ontologies" -H "Authorization: Bearer $TOKEN" | jq '.total')
echo "Loaded Ontologies: $ont_count"
curl -s "$BASE/ontologies" -H "Authorization: Bearer $TOKEN" | jq -r '.ontologies[] | "  - " + .id'
```

---

## Swagger UI

For interactive exploration, visit: **http://localhost:8080/swagger-ui/**

All endpoints are documented there with try-it-out functionality.
