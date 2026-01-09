# Copyright 2026-2026 Penserai Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Common utilities for TesseraiDB examples.

This module provides shared functionality for all example scripts,
including client initialization, logging setup, and helper functions.

Cross-Domain Interoperability:
    This module supports domain-aware twin creation and querying,
    enabling interoperability across different industry domains.

Configuration:
    Set the following environment variables to configure the examples:

    TESSERAI_API_URL: The TesseraiDB API URL (default: https://api.tesserai.io)
    TESSERAI_API_KEY: Your API key (required for authentication)

    You can get your API key from the TesseraiDB console at https://tesserai.io
"""

import sys
import os
import logging
from typing import Optional

import httpx

# Add the SDK to the path if running from source
_sdk_path = os.path.join(os.path.dirname(__file__), '..', 'sdks', 'python')
if os.path.exists(_sdk_path):
    sys.path.insert(0, _sdk_path)

from dtaas import DTaaSClient
from dtaas.exceptions import ConflictError, NotFoundError
from dtaas.models import BatchOperation, BatchOperationType, BatchConfig, BatchRequest, BatchResponse

# Default configuration - uses TesseraiDB Cloud API
DEFAULT_BASE_URL = "https://api.tesserai.io"


# =============================================================================
# Example Domain Namespace Definitions
# =============================================================================
# These are EXAMPLE namespaces used by the sample scenarios in this folder.
# Users should define their own namespaces for their specific use cases.

# Example core namespace
DTAAS_CORE_NS = "http://tesserai.io/ontology/core#"

# Example domain namespaces (customize for your use case)
DOMAIN_NAMESPACES = {
    "automotive": "http://tesserai.io/ontology/automotive#",
    "robotics": "http://tesserai.io/ontology/robotics#",
    "supply_chain": "http://tesserai.io/ontology/supply_chain#",
    "healthcare": "http://tesserai.io/ontology/healthcare#",
    "aerospace": "http://tesserai.io/ontology/aerospace#",
    "smart_building": "http://tesserai.io/ontology/smart_building#",
    "manufacturing": "http://tesserai.io/ontology/manufacturing#",
    "smart_city": "http://tesserai.io/ontology/smart_city#",
    "energy_grid": "http://tesserai.io/ontology/energy_grid#",
    "agriculture": "http://tesserai.io/ontology/agriculture#",
    "finance": "http://tesserai.io/ontology/finance#",
    "taxation": "http://tesserai.io/ontology/taxation#",
}

# Namespace prefixes for SPARQL queries
NAMESPACE_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX dtaas: <http://tesserai.io/ontology/core#>
PREFIX auto: <http://tesserai.io/ontology/automotive#>
PREFIX robo: <http://tesserai.io/ontology/robotics#>
PREFIX supply: <http://tesserai.io/ontology/supply_chain#>
PREFIX health: <http://tesserai.io/ontology/healthcare#>
PREFIX aero: <http://tesserai.io/ontology/aerospace#>
PREFIX bldg: <http://tesserai.io/ontology/smart_building#>
PREFIX mfg: <http://tesserai.io/ontology/manufacturing#>
PREFIX city: <http://tesserai.io/ontology/smart_city#>
PREFIX energy: <http://tesserai.io/ontology/energy_grid#>
PREFIX agri: <http://tesserai.io/ontology/agriculture#>
PREFIX fin: <http://tesserai.io/ontology/finance#>
PREFIX tax: <http://tesserai.io/ontology/taxation#>
"""

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tesserai-examples")


def get_api_key() -> Optional[str]:
    """
    Get the TesseraiDB API key from environment variables.

    Checks TESSERAI_API_KEY first, then falls back to DTAAS_TOKEN for
    backwards compatibility.

    Returns:
        str: The API key, or None if not set
    """
    return os.environ.get("TESSERAI_API_KEY") or os.environ.get("DTAAS_TOKEN")


def get_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
) -> DTaaSClient:
    """
    Create and return a TesseraiDB client.

    Args:
        base_url: The TesseraiDB API URL (default: https://api.tesserai.io)
        api_key: Your API key. If not provided, reads from TESSERAI_API_KEY
                 environment variable.

    Returns:
        DTaaSClient: An initialized client instance

    Raises:
        ValueError: If no API key is provided or found in environment

    Example:
        # Using environment variable (recommended)
        export TESSERAI_API_KEY="your-api-key"
        client = get_client()

        # Or pass directly
        client = get_client(api_key="your-api-key")
    """
    url = base_url or os.environ.get("TESSERAI_API_URL", DEFAULT_BASE_URL)

    logger.info(f"Connecting to TesseraiDB at {url}")

    # Get API key from parameter or environment
    token = api_key or get_api_key()

    if not token:
        raise ValueError(
            "No API key provided. Set TESSERAI_API_KEY environment variable "
            "or pass api_key parameter. Get your API key from https://tesserai.io"
        )

    return DTaaSClient(url, token=token)


def create_twin_safe(client: DTaaSClient, twin_data: dict, upsert: bool = True) -> Optional[dict]:
    """
    Create or update a twin safely.

    By default, uses upsert=True which will replace existing twin data if the
    twin already exists. This ensures the data is always up-to-date.

    Args:
        client: The DTaaS client
        twin_data: The twin data to create
        upsert: If True (default), replace existing twin data. If False, the
                backend will return 409 Conflict if the twin already exists.

    Returns:
        dict: The created or updated twin as a dictionary, or None if conflict
              occurred with upsert=False
    """
    twin_id = twin_data.get("id")
    # Set upsert in the request data
    twin_data_with_upsert = {**twin_data, "upsert": upsert}
    try:
        result = client.twins.create(twin_data_with_upsert)
        if upsert:
            logger.info(f"Created/updated twin: {twin_id}")
        else:
            logger.info(f"Created twin: {twin_id}")
        # Convert Twin model to dict for consistent return type
        return result.model_dump()
    except ConflictError:
        logger.warning(f"Twin '{twin_id}' already exists (use upsert=True to update)")
        return None


def add_relationship_safe(
    client: DTaaSClient,
    source_id: str,
    rel_type: str,
    target_id: str,
    properties: Optional[dict] = None
) -> bool:
    """
    Add a relationship between twins safely.

    Args:
        client: The DTaaS client
        source_id: The source twin ID
        rel_type: The relationship type
        target_id: The target twin ID
        properties: Optional relationship properties

    Returns:
        bool: True if relationship was added, False otherwise
    """
    try:
        client.twins.add_relationship(source_id, rel_type, target_id, properties)
        logger.info(f"Added relationship: {source_id} --[{rel_type}]--> {target_id}")
        return True
    except NotFoundError as e:
        logger.warning(f"Could not add relationship - twin not found: {e}")
        return False
    except ConflictError:
        logger.warning(f"Relationship already exists: {source_id} --[{rel_type}]--> {target_id}")
        return False
    except Exception as e:
        logger.warning(f"Could not add relationship {source_id} -> {target_id}: {e}")
        return False


def print_summary(domain: str, twins_created: int, relationships_created: int, ontologies_uploaded: int = 0) -> None:
    """Print a summary of the seeded data."""
    print("\n" + "=" * 60)
    print(f" {domain} Digital Twin - Seeding Complete")
    print("=" * 60)
    if ontologies_uploaded > 0:
        print(f" Ontologies uploaded:   {ontologies_uploaded}")
    print(f" Twins created:        {twins_created}")
    print(f" Relationships created: {relationships_created}")
    print("=" * 60 + "\n")


def upload_ontology_safe(
    client: DTaaSClient,
    ontology_id: str,
    file_path: str,
    content_type: str = "text/turtle"
) -> bool:
    """
    Upload an ontology file safely using the REST API.

    This uploads ontologies through the API so lineage is properly tracked.

    Args:
        client: The DTaaS client
        ontology_id: Unique identifier for the ontology
        file_path: Path to the ontology file (Turtle format)
        content_type: MIME type (default: text/turtle)

    Returns:
        bool: True if ontology was uploaded, False otherwise
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Use the client's base URL and headers
        url = f"{client._base_url}/api/v1/ontologies/{ontology_id}"
        headers = {
            "Content-Type": content_type,
            "Authorization": f"Bearer {client._token}" if hasattr(client, '_token') and client._token else None,
            "X-Tenant-ID": "default",
        }
        # Remove None headers
        headers = {k: v for k, v in headers.items() if v is not None}

        resp = httpx.post(url, content=content, headers=headers)

        if resp.status_code in (200, 201):
            logger.info(f"Uploaded ontology: {ontology_id} from {file_path}")
            return True
        elif resp.status_code == 409:
            logger.info(f"Ontology {ontology_id} already exists (updating...)")
            # Try PUT/DELETE+POST for update
            return True
        else:
            logger.warning(f"Failed to upload ontology {ontology_id}: {resp.status_code} - {resp.text}")
            return False

    except FileNotFoundError:
        logger.warning(f"Ontology file not found: {file_path}")
        return False
    except Exception as e:
        logger.warning(f"Could not upload ontology {ontology_id}: {e}")
        return False


def cleanup_twins(client: DTaaSClient, twin_ids: list) -> None:
    """
    Delete twins by their IDs (for cleanup purposes).

    Args:
        client: The DTaaS client
        twin_ids: List of twin IDs to delete
    """
    for twin_id in twin_ids:
        try:
            client.twins.delete(twin_id)
            logger.info(f"Deleted twin: {twin_id}")
        except Exception as e:
            logger.warning(f"Could not delete twin {twin_id}: {e}")


# =============================================================================
# Domain-Aware Helper Functions
# =============================================================================

def get_domain_namespace(domain: str) -> str:
    """
    Get the namespace URI for a domain.

    Args:
        domain: The domain name (e.g., 'automotive', 'robotics')

    Returns:
        str: The namespace URI for the domain

    Raises:
        ValueError: If the domain is not recognized
    """
    if domain not in DOMAIN_NAMESPACES:
        raise ValueError(
            f"Unknown domain: {domain}. "
            f"Valid domains: {', '.join(DOMAIN_NAMESPACES.keys())}"
        )
    return DOMAIN_NAMESPACES[domain]


def expand_type(domain: str, local_name: str) -> str:
    """
    Expand a local type name to a full URI using the domain namespace.

    Args:
        domain: The domain name (e.g., 'automotive', 'robotics')
        local_name: The local type name (e.g., 'FleetVehicle', 'AMR')

    Returns:
        str: The full URI (e.g., 'http://tesserai.io/ontology/automotive#FleetVehicle')
    """
    namespace = get_domain_namespace(domain)
    return f"{namespace}{local_name}"


def expand_core_type(local_name: str) -> str:
    """
    Expand a local type name to a full URI using the core namespace.

    Args:
        local_name: The local type name (e.g., 'Vehicle', 'Sensor')

    Returns:
        str: The full URI (e.g., 'http://tesserai.io/ontology/core#Vehicle')
    """
    return f"{DTAAS_CORE_NS}{local_name}"


def create_domain_twin(
    client: DTaaSClient,
    domain: str,
    twin_id: str,
    twin_type: str,
    name: str,
    description: Optional[str] = None,
    properties: Optional[dict] = None,
) -> dict:
    """
    Create a domain-aware twin with proper namespace and domain tagging.

    Args:
        client: The DTaaS client
        domain: The domain this twin belongs to (e.g., 'automotive', 'robotics')
        twin_id: Unique identifier for the twin
        twin_type: The type name (will be expanded with domain namespace)
        name: Human-readable name
        description: Optional description
        properties: Optional additional properties

    Returns:
        dict: The created twin as a dictionary
    """
    # Expand type to full URI if not already
    full_type = twin_type if "://" in twin_type else expand_type(domain, twin_type)

    twin_data = {
        "id": twin_id,
        "type": full_type,
        "name": name,
        "domain": domain,
        "properties": properties or {},
    }
    if description:
        twin_data["description"] = description

    return create_twin_safe(client, twin_data)


def list_twins_by_domain(client: DTaaSClient, domain: str) -> list:
    """
    List all twins belonging to a specific domain.

    Args:
        client: The DTaaS client
        domain: The domain to filter by (e.g., 'automotive', 'robotics')

    Returns:
        list: List of Twin objects in the specified domain
    """
    return client.twins.list(domain=domain)


def get_all_domains() -> list[str]:
    """
    Get a list of all supported domains.

    Returns:
        list: List of domain names
    """
    return list(DOMAIN_NAMESPACES.keys())


def print_domain_summary(client: DTaaSClient) -> None:
    """
    Print a summary of twins across all domains.

    Args:
        client: The DTaaS client
    """
    print("\n" + "=" * 70)
    print(" Cross-Domain Digital Twin Summary")
    print("=" * 70)

    total = 0
    for domain in DOMAIN_NAMESPACES.keys():
        twins = list_twins_by_domain(client, domain)
        count = len(twins)
        total += count
        if count > 0:
            print(f"  {domain:20} : {count:4} twins")

    print("-" * 70)
    print(f"  {'TOTAL':20} : {total:4} twins")
    print("=" * 70 + "\n")


# =============================================================================
# Bulk Operations (Performance Optimization)
# =============================================================================

def bulk_create_twins(client: DTaaSClient, twins_data: list[dict], upsert: bool = True) -> tuple[int, int]:
    """
    Create multiple twins in a single batch request.

    This is significantly faster than creating twins one at a time, especially
    when connecting to a remote API.

    Note: The batch API's CreateTwin operation does NOT support upsert directly.
    When upsert=True, this function first deletes existing twins, then creates
    new ones with fresh data (following the pattern documented in batch.rs).

    Args:
        client: The DTaaS client
        twins_data: List of twin data dictionaries, each containing at minimum 'id'
        upsert: If True (default), delete existing twins before creating new ones

    Returns:
        tuple: (successful_count, failed_count)
    """
    if not twins_data:
        return 0, 0

    # Collect twin IDs for upsert (delete-then-create pattern)
    twin_ids = []
    for i, twin_data in enumerate(twins_data):
        twin_id = twin_data.get("id")
        if not twin_id:
            logger.warning(f"Skipping twin at index {i}: missing 'id'")
            continue
        twin_ids.append(twin_id)

    # Step 1: If upsert=True, delete existing twins first
    if upsert and twin_ids:
        delete_operations = [
            BatchOperation(
                id=f"delete-{twin_id}",
                operation=BatchOperationType.DELETE_TWIN,
                resource_id=twin_id,
                payload={}
            )
            for twin_id in twin_ids
        ]

        # Process deletes in batches
        batch_size = 100
        for i in range(0, len(delete_operations), batch_size):
            batch_ops = delete_operations[i:i + batch_size]
            request = BatchRequest(
                operations=batch_ops,
                config=BatchConfig(stop_on_error=False, parallel=True)
            )
            try:
                client.batch.process(request)
                # Don't log delete failures - twins may not exist yet
            except Exception as e:
                logger.debug(f"Delete batch request (expected if twins don't exist): {e}")

    # Step 2: Build create operations
    operations = []
    for i, twin_data in enumerate(twins_data):
        twin_id = twin_data.get("id")
        if not twin_id:
            continue  # Already warned above

        # Convert twin data to RDF-compatible format for the batch API
        # The batch API expects: { "id": "twin-id", "data": "RDF data" }
        # We'll use JSON-LD style embedding
        properties = twin_data.get("properties", {})
        twin_type = twin_data.get("type", "")
        name = twin_data.get("name", "")
        description = twin_data.get("description", "")
        domain = twin_data.get("domain", "")

        # Build a simple Turtle representation
        turtle_lines = [
            f'@prefix dtaas: <http://tesserai.io/ontology/core#> .',
            f'@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
            f'@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
            f'',
            f'<urn:tesserai:twin:{twin_id}> a <{twin_type}> .' if twin_type else '',
        ]

        if name:
            # Escape quotes in name
            escaped_name = name.replace('\\', '\\\\').replace('"', '\\"')
            turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> rdfs:label "{escaped_name}" .')

        if description:
            escaped_desc = description.replace('\\', '\\\\').replace('"', '\\"')
            turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> rdfs:comment "{escaped_desc}" .')

        if domain:
            turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> dtaas:domain "{domain}" .')

        # Add properties
        for key, value in properties.items():
            if isinstance(value, bool):
                turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> dtaas:{key} {str(value).lower()} .')
            elif isinstance(value, (int, float)):
                turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> dtaas:{key} {value} .')
            elif isinstance(value, str):
                escaped_val = value.replace('\\', '\\\\').replace('"', '\\"')
                turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> dtaas:{key} "{escaped_val}" .')
            elif isinstance(value, dict):
                # Store complex objects as JSON strings
                import json
                json_str = json.dumps(value).replace('\\', '\\\\').replace('"', '\\"')
                turtle_lines.append(f'<urn:tesserai:twin:{twin_id}> dtaas:{key} "{json_str}" .')

        turtle_data = '\n'.join(line for line in turtle_lines if line)

        operations.append(BatchOperation(
            id=f"create-{twin_id}",
            operation=BatchOperationType.CREATE_TWIN,
            payload={"id": twin_id, "data": turtle_data}
        ))

    if not operations:
        return 0, 0

    # Process in batches of 100 to avoid overwhelming the server
    batch_size = 100
    total_succeeded = 0
    total_failed = 0

    for i in range(0, len(operations), batch_size):
        batch_ops = operations[i:i + batch_size]
        request = BatchRequest(
            operations=batch_ops,
            config=BatchConfig(stop_on_error=False, parallel=True)
        )

        try:
            response: BatchResponse = client.batch.process(request)
            total_succeeded += response.succeeded
            total_failed += response.failed

            # Log failures
            for result in response.results:
                if not result.success:
                    logger.warning(f"Failed to create twin: {result.id} - {result.error}")

            logger.info(f"Batch {i // batch_size + 1}: {response.succeeded}/{len(batch_ops)} twins created in {response.total_duration_ms}ms")
        except Exception as e:
            logger.error(f"Batch request failed: {e}")
            total_failed += len(batch_ops)

    return total_succeeded, total_failed


def create_twins_with_lineage(
    client: DTaaSClient,
    twins_data: list[dict],
    upsert: bool = True
) -> tuple[int, int]:
    """
    Create multiple twins using individual API calls to ensure lineage tracking.

    Unlike bulk_create_twins which uses the batch API, this function creates
    each twin individually via POST /api/v1/twins/json, ensuring that
    TwinCreation activities and source lineage edges are properly recorded.

    Use this when lineage tracking is important. For pure performance when
    lineage is not needed, use bulk_create_twins instead.

    Args:
        client: The DTaaS client
        twins_data: List of twin data dictionaries, each containing at minimum 'id'
        upsert: If True (default), replace existing twin data

    Returns:
        tuple: (successful_count, failed_count)
    """
    if not twins_data:
        return 0, 0

    succeeded = 0
    failed = 0

    for twin_data in twins_data:
        result = create_twin_safe(client, twin_data, upsert=upsert)
        if result is not None:
            succeeded += 1
        else:
            failed += 1

    logger.info(f"Created {succeeded}/{len(twins_data)} twins with lineage tracking")
    return succeeded, failed


def bulk_add_relationships(
    client: DTaaSClient,
    relationships: list[tuple[str, str, str, Optional[dict]]],
    batch_size: int = 100
) -> tuple[int, int]:
    """
    Add multiple relationships using the batch API with ADD_TRIPLES operations.

    Groups relationships by source twin and creates batch operations to minimize
    HTTP round-trips.

    Args:
        client: The DTaaS client
        relationships: List of (source_id, rel_type, target_id, properties) tuples
        batch_size: Number of operations per batch request (default 100)

    Returns:
        tuple: (successful_count, failed_count)
    """
    if not relationships:
        return 0, 0

    from collections import defaultdict

    # Group relationships by source twin
    by_source: dict[str, list[tuple[str, str, Optional[dict]]]] = defaultdict(list)
    for source_id, rel_type, target_id, properties in relationships:
        by_source[source_id].append((rel_type, target_id, properties))

    # Build batch operations - one ADD_TRIPLES per source twin
    operations = []
    relationship_counts = {}  # Track how many relationships per operation

    for source_id, rels in by_source.items():
        # Generate Turtle RDF for all relationships from this source
        turtle_lines = []
        for rel_type, target_id, properties in rels:
            # Expand relationship type to full URI if needed
            if "://" not in rel_type:
                rel_uri = f"http://tesserai.io/ontology/core#{rel_type}"
            else:
                rel_uri = rel_type

            # Target URI
            if "://" not in target_id:
                target_uri = f"urn:tesserai:twin:{target_id}"
            else:
                target_uri = target_id

            turtle_lines.append(f'<urn:tesserai:twin:{source_id}> <{rel_uri}> <{target_uri}> .')

            # Add relationship properties if any
            if properties:
                for key, value in properties.items():
                    if isinstance(value, str):
                        escaped_val = value.replace('\\', '\\\\').replace('"', '\\"')
                        turtle_lines.append(f'<urn:tesserai:twin:{source_id}> <http://tesserai.io/ontology/core#{key}> "{escaped_val}" .')
                    elif isinstance(value, bool):
                        turtle_lines.append(f'<urn:tesserai:twin:{source_id}> <http://tesserai.io/ontology/core#{key}> {str(value).lower()} .')
                    elif isinstance(value, (int, float)):
                        turtle_lines.append(f'<urn:tesserai:twin:{source_id}> <http://tesserai.io/ontology/core#{key}> {value} .')

        turtle_data = "\n".join(turtle_lines)
        op_id = f"rel-{source_id}"

        operations.append(BatchOperation(
            id=op_id,
            operation=BatchOperationType.ADD_TRIPLES,
            resource_id=source_id,
            payload={"data": turtle_data}
        ))
        relationship_counts[op_id] = len(rels)

    # Execute in batches
    total_succeeded = 0
    total_failed = 0

    for i in range(0, len(operations), batch_size):
        batch_ops = operations[i:i + batch_size]

        try:
            request = BatchRequest(
                operations=batch_ops,
                config=BatchConfig(stop_on_error=False, parallel=True)
            )
            response = client.batch.process(request)

            for result in response.results:
                rel_count = relationship_counts.get(result.id, 1)
                if result.success:
                    total_succeeded += rel_count
                else:
                    total_failed += rel_count
                    logger.warning(f"Failed to add relationships for {result.id}: {result.error}")

            logger.info(f"Batch {i // batch_size + 1}: {response.succeeded}/{len(batch_ops)} operations in {response.total_duration_ms}ms")
        except Exception as e:
            logger.error(f"Batch request failed: {e}")
            # Count failed relationships
            for op in batch_ops:
                total_failed += relationship_counts.get(op.id, 1)

    logger.info(f"Added {total_succeeded}/{len(relationships)} relationships")
    return total_succeeded, total_failed


def bulk_upload_ontologies(
    base_url: str,
    token: str,
    ontologies: list[tuple[str, str, str]],
    tenant_id: str = "default"
) -> tuple[int, int]:
    """
    Upload multiple ontologies in parallel.

    Args:
        base_url: The DTaaS server URL
        token: Authentication token
        ontologies: List of (ontology_id, file_path, description) tuples
        tenant_id: Tenant ID (default: "default")

    Returns:
        tuple: (successful_count, failed_count)
    """
    if not ontologies:
        return 0, 0

    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def upload_one(ont: tuple) -> bool:
        ontology_id, file_path, description = ont
        full_path = Path(file_path)

        if not full_path.exists():
            logger.warning(f"Ontology file not found: {full_path}")
            return False

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                ontology_data = f.read()

            with httpx.Client(timeout=60.0) as http:
                response = http.post(
                    f"{base_url}/api/v1/ontologies/{ontology_id}",
                    content=ontology_data,
                    headers={
                        "Content-Type": "text/turtle",
                        "Authorization": f"Bearer {token}",
                        "X-Tenant-ID": tenant_id
                    }
                )

                if response.status_code in (200, 201):
                    logger.info(f"Loaded ontology: {ontology_id}")
                    return True
                else:
                    logger.error(f"Failed to load ontology {ontology_id}: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error loading ontology {ontology_id}: {e}")
            return False

    succeeded = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(upload_one, ont): ont for ont in ontologies}
        for future in as_completed(futures):
            if future.result():
                succeeded += 1
            else:
                failed += 1

    logger.info(f"Loaded {succeeded}/{len(ontologies)} ontologies")
    return succeeded, failed
