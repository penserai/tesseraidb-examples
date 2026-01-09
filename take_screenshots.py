#!/usr/bin/env python3
"""
Screenshot Automation for Web UI Dashboards

This script takes screenshots of all web UI dashboards for documentation.
It requires the DTaaS server to be running and each example to be seeded.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    # Take all screenshots (requires server running and data seeded)
    python take_screenshots.py

    # Take screenshot of specific dashboard
    python take_screenshots.py --dashboard energy_grid

    # List available dashboards
    python take_screenshots.py --list
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright is required. Install with:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)

# Dashboard configurations
DASHBOARDS = {
    "energy_grid": {
        "port": 8110,
        "name": "Energy Grid Dashboard",
        "description": "Power generation, grid load, renewable sources"
    },
    "smart_building": {
        "port": 8082,
        "name": "Smart Building Dashboard",
        "description": "HVAC status, zone temperatures, occupancy"
    },
    "supply_chain": {
        "port": 8102,
        "name": "Supply Chain Dashboard",
        "description": "Warehouses, shipments, inventory levels"
    },
    "manufacturing": {
        "port": 8104,
        "name": "Manufacturing Dashboard",
        "description": "Production lines, QC metrics, energy usage"
    },
    "healthcare": {
        "port": 8088,
        "name": "Healthcare Dashboard",
        "description": "Departments, ORs, imaging equipment"
    },
    "finance": {
        "port": 8106,
        "name": "Finance Dashboard",
        "description": "Trading desks, P&L, risk limits"
    },
    "smart_city": {
        "port": 8092,
        "name": "Smart City Dashboard",
        "description": "Transit, traffic, utilities"
    },
    "automotive": {
        "port": 8094,
        "name": "Automotive Dashboard",
        "description": "Fleet status, EVs, charging"
    },
    "aerospace": {
        "port": 8096,
        "name": "Aerospace Dashboard",
        "description": "Satellite constellation, ground stations"
    },
    "agriculture": {
        "port": 8098,
        "name": "Agriculture Dashboard",
        "description": "Fields, crops, irrigation, drones"
    },
    "taxation": {
        "port": 8100,
        "name": "Taxation Dashboard",
        "description": "Transfer pricing, entities, benchmarking"
    },
    "alerting_system": {
        "port": 8085,
        "name": "Alerting System Dashboard",
        "description": "Real-time alerts, thresholds, notifications"
    },
    "predictive_maintenance": {
        "port": 8090,
        "name": "Predictive Maintenance Dashboard",
        "description": "Equipment health, failure prediction, work orders"
    },
    "cascading_failure": {
        "port": 8108,
        "name": "Cascading Failure Dashboard",
        "description": "Infrastructure dependencies, failure simulation"
    },
}

SCRIPT_DIR = Path(__file__).parent
SCREENSHOTS_DIR = SCRIPT_DIR / "screenshots"


async def take_screenshot(domain: str, config: dict) -> bool:
    """Take a screenshot of a single dashboard."""
    port = config["port"]
    url = f"http://localhost:{port}"
    output_path = SCREENSHOTS_DIR / f"{domain}_dashboard.png"

    print(f"\n{'='*60}")
    print(f"  {config['name']}")
    print(f"  URL: {url}")
    print(f"{'='*60}")

    # Start the web UI process
    web_ui_path = SCRIPT_DIR / domain / "web_ui.py"
    if not web_ui_path.exists():
        print(f"  [ERROR] web_ui.py not found at {web_ui_path}")
        return False

    print(f"  Starting web UI on port {port}...")
    process = subprocess.Popen(
        [sys.executable, str(web_ui_path), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(SCRIPT_DIR)
    )

    try:
        # Wait for server to start
        await asyncio.sleep(5)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            try:
                print(f"  Loading dashboard...")
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for WebSocket data to load
                await asyncio.sleep(8)

                # Take screenshot
                print(f"  Taking screenshot...")
                await page.screenshot(path=str(output_path), full_page=True)

                print(f"  [OK] Saved to {output_path}")
                success = True

            except Exception as e:
                print(f"  [ERROR] Failed to capture: {e}")
                success = False

            finally:
                await browser.close()

    finally:
        # Terminate the web UI process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    return success


async def take_all_screenshots(domains: list = None):
    """Take screenshots of all (or specified) dashboards."""
    if domains is None:
        domains = list(DASHBOARDS.keys())

    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    results = {}
    for domain in domains:
        if domain not in DASHBOARDS:
            print(f"Unknown dashboard: {domain}")
            continue

        success = await take_screenshot(domain, DASHBOARDS[domain])
        results[domain] = success

    # Summary
    print(f"\n{'='*60}")
    print("  SCREENSHOT SUMMARY")
    print(f"{'='*60}")

    successful = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    for domain, success in results.items():
        status = "[OK]" if success else "[FAILED]"
        print(f"  {status} {domain}")

    print(f"\n  Total: {successful} successful, {failed} failed")
    print(f"  Screenshots saved to: {SCREENSHOTS_DIR}")


def list_dashboards():
    """List all available dashboards."""
    print("\nAvailable Dashboards:")
    print("-" * 70)
    print(f"{'Domain':<15} {'Port':<8} {'Description'}")
    print("-" * 70)
    for domain, config in DASHBOARDS.items():
        print(f"{domain:<15} {config['port']:<8} {config['description']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Take screenshots of web UI dashboards"
    )
    parser.add_argument(
        "--dashboard", "-d",
        help="Take screenshot of specific dashboard(s)",
        nargs="*"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available dashboards"
    )
    args = parser.parse_args()

    if args.list:
        list_dashboards()
        return

    print("\n" + "=" * 60)
    print("  Web UI Dashboard Screenshot Automation")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  1. DTaaS server running on localhost:8080")
    print("  2. Example data seeded (run seed.py for each domain)")
    print("  3. Playwright installed (pip install playwright)")
    print()

    if args.dashboard:
        asyncio.run(take_all_screenshots(args.dashboard))
    else:
        asyncio.run(take_all_screenshots())


if __name__ == "__main__":
    main()
