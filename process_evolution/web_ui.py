#!/usr/bin/env python3
"""
Business Process Evolution - Interactive Web UI

A web dashboard for visualizing process management including:
- Process definitions and versions
- Execution logs with performance metrics
- Bottleneck detection and analysis
- Process evolution history

Usage:
    python web_ui.py [--port 8124]

Then open http://localhost:8124 in your browser.

Requires:
    pip install websockets
"""

import asyncio
import json
import argparse
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
from typing import Dict, Set
from collections import defaultdict

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Configuration
AGENT_ID = "process-manager-corp"
HTTP_PORT = 8124
WS_PORT = 8125

# Global state
client = None
connected_clients: Set = set()
memories_cache: Dict = {}


def load_memories():
    """Load memories from TesseraiDB."""
    global memories_cache

    try:
        result = client.memory.query(
            agent_id=AGENT_ID,
            query={"limit": 500}
        )

        memories_cache = {}
        for mem in result.memories:
            mem_dict = mem.model_dump() if hasattr(mem, 'model_dump') else mem
            memories_cache[mem_dict["id"]] = mem_dict

        logger.info(f"Loaded {len(memories_cache)} memories")

    except Exception as e:
        logger.error(f"Failed to load memories: {e}")


def get_dashboard_data() -> dict:
    """Get dashboard summary data."""
    processes = []
    executions = []
    bottlenecks = []
    evolutions = []

    # Aggregate execution stats by process and step
    step_stats = defaultdict(lambda: {"durations": [], "delays": 0})

    for mem in memories_cache.values():
        topics = mem.get("topics", [])
        mem_type = mem.get("memory_type")
        record_type = mem.get("record_type")
        metadata = mem.get("metadata", {})

        if record_type == "procedure" and "process-definition" in topics:
            processes.append({
                "id": metadata.get("process_id", mem["id"]),
                "content": mem["content"][:100],
                "version": mem.get("version", 1),
                "supersedes": metadata.get("supersedes"),
            })
        elif "process-log" in topics and mem_type == "episodic":
            executions.append({
                "id": metadata.get("execution_id", ""),
                "process": metadata.get("process_id", ""),
                "step": metadata.get("step", ""),
                "duration": metadata.get("duration_hours", 0),
                "expected": metadata.get("expected_hours", 0),
                "is_delay": metadata.get("is_delay", False),
            })
            # Aggregate stats
            key = f"{metadata.get('process_id', '')}-{metadata.get('step', '')}"
            step_stats[key]["durations"].append(metadata.get("duration_hours", 0))
            if metadata.get("is_delay"):
                step_stats[key]["delays"] += 1

        elif "bottleneck" in topics and mem_type == "semantic":
            bottlenecks.append({
                "content": mem["content"][:150],
                "confidence": mem.get("confidence", 0),
                "evidence_count": metadata.get("evidence_count", 0),
            })
        elif "evolution" in topics and record_type == "procedure":
            evolutions.append({
                "content": mem["content"][:100],
                "change": metadata.get("change", ""),
                "reason": metadata.get("reason", ""),
                "supersedes": metadata.get("supersedes", ""),
            })

    # Calculate step averages
    step_performance = []
    for key, stats in step_stats.items():
        if stats["durations"]:
            avg = sum(stats["durations"]) / len(stats["durations"])
            process_id, step = key.rsplit("-", 1) if "-" in key else (key, "unknown")
            step_performance.append({
                "process": process_id,
                "step": step,
                "avg_hours": round(avg, 1),
                "delay_count": stats["delays"],
                "total_runs": len(stats["durations"]),
            })

    step_performance.sort(key=lambda x: x["avg_hours"], reverse=True)

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "processes": processes,
        "executions": executions[:20],
        "bottlenecks": bottlenecks,
        "evolutions": evolutions,
        "step_performance": step_performance[:10],
        "delay_count": sum(1 for e in executions if e["is_delay"]),
    }


async def websocket_handler(websocket):
    """Handle WebSocket connections."""
    connected_clients.add(websocket)

    try:
        await websocket.send(json.dumps({
            "type": "init",
            "data": get_dashboard_data()
        }))

        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg.get("type") == "refresh":
                    load_memories()
                    await websocket.send(json.dumps({
                        "type": "init",
                        "data": get_dashboard_data()
                    }))
            except json.JSONDecodeError:
                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)


# HTML Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Process Evolution - TesseraiDB</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold text-emerald-400">Process Evolution</h1>
                <p class="text-gray-400 mt-1">Business Process Intelligence Dashboard</p>
            </div>
            <div class="flex items-center gap-4">
                <span id="connection-status" class="px-3 py-1 rounded-full text-sm bg-yellow-500/20 text-yellow-400">Connecting...</span>
                <button onclick="refresh()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg transition">Refresh</button>
            </div>
        </div>

        <!-- Stats Row -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-white" id="stat-total">-</div>
                <div class="text-gray-400 text-sm">Total Memories</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-blue-400" id="stat-processes">-</div>
                <div class="text-gray-400 text-sm">Processes</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-red-400" id="stat-delays">-</div>
                <div class="text-gray-400 text-sm">Delays Detected</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-green-400" id="stat-evolutions">-</div>
                <div class="text-gray-400 text-sm">Evolutions</div>
            </div>
        </div>

        <!-- Main Grid -->
        <div class="grid lg:grid-cols-2 gap-8">
            <!-- Process Definitions -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-blue-500 rounded-full"></span>
                    Process Definitions
                </h2>
                <div id="processes-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Step Performance -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-orange-500 rounded-full"></span>
                    Step Performance (Slowest)
                </h2>
                <div id="performance-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Bottleneck Analysis -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-red-500 rounded-full"></span>
                    Bottleneck Analysis
                </h2>
                <div id="bottlenecks-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Process Evolutions -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-green-500 rounded-full"></span>
                    Process Evolutions
                </h2>
                <div id="evolutions-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws;
        const WS_PORT = """ + str(WS_PORT) + """;

        function connect() {
            ws = new WebSocket(`ws://localhost:${WS_PORT}`);

            ws.onopen = () => {
                document.getElementById('connection-status').className = 'px-3 py-1 rounded-full text-sm bg-green-500/20 text-green-400';
                document.getElementById('connection-status').textContent = 'Connected';
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'px-3 py-1 rounded-full text-sm bg-red-500/20 text-red-400';
                document.getElementById('connection-status').textContent = 'Disconnected';
                setTimeout(connect, 3000);
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'init') updateDashboard(msg.data);
            };
        }

        function updateDashboard(data) {
            document.getElementById('stat-total').textContent = data.total_memories;
            document.getElementById('stat-processes').textContent = data.processes.length;
            document.getElementById('stat-delays').textContent = data.delay_count;
            document.getElementById('stat-evolutions').textContent = data.evolutions.length;

            // Processes
            document.getElementById('processes-list').innerHTML = data.processes.map(p => `
                <div class="bg-gray-700 rounded-lg p-3">
                    <div class="flex justify-between items-start">
                        <div class="text-sm text-gray-200">${escapeHtml(p.content)}</div>
                        <span class="text-xs px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded">v${p.version}</span>
                    </div>
                    ${p.supersedes ? `<div class="text-xs text-gray-500 mt-1">Supersedes: ${p.supersedes}</div>` : ''}
                </div>
            `).join('') || '<p class="text-gray-500">No processes defined</p>';

            // Step Performance
            document.getElementById('performance-list').innerHTML = data.step_performance.map(s => {
                const delayPct = s.total_runs > 0 ? (s.delay_count / s.total_runs * 100).toFixed(0) : 0;
                return `
                <div class="bg-gray-700 rounded-lg p-3">
                    <div class="flex justify-between items-center">
                        <div>
                            <div class="text-sm text-gray-200">${escapeHtml(s.step)}</div>
                            <div class="text-xs text-gray-500">${s.process}</div>
                        </div>
                        <div class="text-right">
                            <div class="text-lg font-bold ${s.delay_count > 0 ? 'text-red-400' : 'text-green-400'}">${s.avg_hours}h</div>
                            <div class="text-xs text-gray-500">${s.delay_count}/${s.total_runs} delays</div>
                        </div>
                    </div>
                    <div class="mt-2 bg-gray-600 h-2 rounded">
                        <div class="bg-red-500 h-2 rounded" style="width: ${delayPct}%"></div>
                    </div>
                </div>
            `}).join('') || '<p class="text-gray-500">No performance data</p>';

            // Bottlenecks
            document.getElementById('bottlenecks-list').innerHTML = data.bottlenecks.map(b => `
                <div class="bg-gray-700 rounded-lg p-3 border-l-4 border-red-500">
                    <div class="text-sm text-gray-200">${escapeHtml(b.content)}</div>
                    <div class="flex items-center gap-2 mt-2">
                        <span class="text-xs text-gray-400">${(b.confidence * 100).toFixed(0)}% confidence</span>
                        <span class="text-xs text-gray-400">•</span>
                        <span class="text-xs text-gray-400">${b.evidence_count} evidence</span>
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No bottlenecks detected</p>';

            // Evolutions
            document.getElementById('evolutions-list').innerHTML = data.evolutions.map(e => `
                <div class="bg-gray-700 rounded-lg p-3 border-l-4 border-green-500">
                    <div class="text-sm text-gray-200 font-medium">${escapeHtml(e.change || e.content)}</div>
                    <div class="text-xs text-gray-400 mt-1">${escapeHtml(e.reason)}</div>
                    ${e.supersedes ? `<div class="text-xs text-green-400 mt-1">Evolved from: ${e.supersedes}</div>` : ''}
                </div>
            `).join('') || '<p class="text-gray-500">No evolutions yet</p>';
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        function refresh() {
            ws.send(JSON.stringify({ type: 'refresh' }));
        }

        connect();
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def run_http_server(port: int):
    server = HTTPServer(("", port), DashboardHandler)
    server.serve_forever()


async def main(http_port: int, ws_port: int):
    global client, HTTP_PORT, WS_PORT

    HTTP_PORT = http_port
    WS_PORT = ws_port

    client = get_client()
    load_memories()

    http_thread = threading.Thread(target=run_http_server, args=(http_port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print("  PROCESS EVOLUTION - WEB UI")
    print(f"{'='*60}")
    print(f"\n  Dashboard: http://localhost:{http_port}")
    print(f"  WebSocket: ws://localhost:{ws_port}")
    print(f"\n  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    async with websockets.serve(websocket_handler, "localhost", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Evolution Web UI")
    parser.add_argument("--port", type=int, default=8124, help="HTTP port")
    parser.add_argument("--ws-port", type=int, default=8125, help="WebSocket port")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port, args.ws_port))
    except KeyboardInterrupt:
        print("\nShutting down...")
