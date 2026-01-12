#!/usr/bin/env python3
"""
Personal Assistant - Interactive Web UI

A web dashboard for visualizing personal assistant memory including:
- User preferences and dietary restrictions
- Active reminders with context triggers
- Location history timeline
- Context-based search

Usage:
    python web_ui.py [--port 8122]

Then open http://localhost:8122 in your browser.

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

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Configuration
AGENT_ID = "assistant-user-alex"
HTTP_PORT = 8122
WS_PORT = 8123

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
    preferences = []
    reminders = []
    location_history = []
    habits = []

    for mem in memories_cache.values():
        topics = mem.get("topics", [])
        mem_type = mem.get("memory_type")
        metadata = mem.get("metadata", {})

        if "food-preference" in topics or "dietary-restriction" in topics:
            preferences.append(mem)
        elif "reminder" in topics or metadata.get("type") == "reminder":
            reminders.append(mem)
        elif "location-history" in topics:
            location_history.append(mem)
        elif "habit" in topics:
            habits.append(mem)
        elif mem_type == "semantic" and "preference" in topics:
            preferences.append(mem)

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "preferences": [{"content": p["content"], "topics": p.get("topics", [])} for p in preferences],
        "reminders": [{"content": r["content"], "context": r.get("context", ""), "priority": r.get("metadata", {}).get("priority", "medium")} for r in reminders],
        "location_history": [{"content": l["content"], "metadata": l.get("metadata", {})} for l in location_history[:10]],
        "habits": [{"content": h["content"], "confidence": h.get("confidence", 0)} for h in habits],
    }


def search_by_context(context: str) -> list:
    """Search memories relevant to a context."""
    try:
        result = client.memory.query(
            agent_id=AGENT_ID,
            query={
                "query": f"relevant to {context}",
                "limit": 20,
                "min_relevance": 0.5,
            }
        )
        return [m.model_dump() if hasattr(m, 'model_dump') else m for m in result.memories]
    except Exception as e:
        logger.error(f"Context search failed: {e}")
        return []


async def websocket_handler(websocket):
    """Handle WebSocket connections."""
    connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        await websocket.send(json.dumps({
            "type": "init",
            "data": get_dashboard_data()
        }))

        async for message in websocket:
            try:
                msg = json.loads(message)
                msg_type = msg.get("type")

                if msg_type == "context_search":
                    context = msg.get("context", "")
                    results = search_by_context(context)
                    await websocket.send(json.dumps({
                        "type": "context_results",
                        "context": context,
                        "results": results
                    }))

                elif msg_type == "refresh":
                    load_memories()
                    await websocket.send(json.dumps({
                        "type": "init",
                        "data": get_dashboard_data()
                    }))

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")

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
    <title>Personal Assistant - TesseraiDB</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold text-violet-400">Personal Assistant</h1>
                <p class="text-gray-400 mt-1">Context-Aware Memory Dashboard</p>
            </div>
            <div class="flex items-center gap-4">
                <span id="connection-status" class="px-3 py-1 rounded-full text-sm bg-yellow-500/20 text-yellow-400">Connecting...</span>
                <button onclick="refresh()" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg transition">Refresh</button>
            </div>
        </div>

        <!-- Context Simulator -->
        <div class="bg-gray-800 rounded-xl p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4">Context Simulator</h2>
            <p class="text-gray-400 text-sm mb-4">Simulate arriving at a location to see relevant memories</p>
            <div class="flex flex-wrap gap-2">
                <button onclick="triggerContext('grocery store')" class="px-4 py-2 bg-green-600/20 text-green-400 border border-green-600/30 rounded-lg hover:bg-green-600/30 transition">Grocery Store</button>
                <button onclick="triggerContext('coffee shop')" class="px-4 py-2 bg-amber-600/20 text-amber-400 border border-amber-600/30 rounded-lg hover:bg-amber-600/30 transition">Coffee Shop</button>
                <button onclick="triggerContext('office')" class="px-4 py-2 bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded-lg hover:bg-blue-600/30 transition">Office</button>
                <button onclick="triggerContext('gym')" class="px-4 py-2 bg-pink-600/20 text-pink-400 border border-pink-600/30 rounded-lg hover:bg-pink-600/30 transition">Gym</button>
                <button onclick="triggerContext('restaurant')" class="px-4 py-2 bg-orange-600/20 text-orange-400 border border-orange-600/30 rounded-lg hover:bg-orange-600/30 transition">Restaurant</button>
                <button onclick="triggerContext('home')" class="px-4 py-2 bg-purple-600/20 text-purple-400 border border-purple-600/30 rounded-lg hover:bg-purple-600/30 transition">Home</button>
            </div>
            <div id="context-results" class="mt-4 hidden">
                <h3 class="text-lg font-medium mb-3">Relevant at <span id="current-context" class="text-violet-400"></span></h3>
                <div id="context-list" class="space-y-2"></div>
            </div>
        </div>

        <!-- Main Grid -->
        <div class="grid md:grid-cols-2 gap-8">
            <!-- Preferences -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-purple-500 rounded-full"></span>
                    User Preferences
                </h2>
                <div id="preferences-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Reminders -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-orange-500 rounded-full"></span>
                    Active Reminders
                </h2>
                <div id="reminders-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Location History -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-blue-500 rounded-full"></span>
                    Recent Visits
                </h2>
                <div id="location-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Habits -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 bg-green-500 rounded-full"></span>
                    Learned Habits
                </h2>
                <div id="habits-list" class="space-y-3">
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
                handleMessage(msg);
            };
        }

        function handleMessage(msg) {
            if (msg.type === 'init') {
                updateDashboard(msg.data);
            } else if (msg.type === 'context_results') {
                showContextResults(msg.context, msg.results);
            }
        }

        function updateDashboard(data) {
            // Preferences
            document.getElementById('preferences-list').innerHTML = data.preferences.map(p => `
                <div class="bg-gray-700 rounded-lg p-3">
                    <div class="text-sm text-gray-200">${escapeHtml(p.content)}</div>
                    <div class="flex gap-1 mt-2">
                        ${p.topics.slice(0,3).map(t => `<span class="text-xs px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No preferences found</p>';

            // Reminders
            document.getElementById('reminders-list').innerHTML = data.reminders.map(r => `
                <div class="bg-gray-700 rounded-lg p-3 border-l-4 ${getPriorityColor(r.priority)}">
                    <div class="text-sm text-gray-200 font-medium">${escapeHtml(r.content)}</div>
                    <div class="text-xs text-gray-400 mt-1">${escapeHtml(r.context)}</div>
                </div>
            `).join('') || '<p class="text-gray-500">No reminders found</p>';

            // Location History
            document.getElementById('location-list').innerHTML = data.location_history.map(l => `
                <div class="bg-gray-700 rounded-lg p-3 flex justify-between items-center">
                    <span class="text-sm text-gray-200">${escapeHtml(l.content)}</span>
                    <span class="text-xs text-gray-400">${l.metadata?.duration_mins || ''}min</span>
                </div>
            `).join('') || '<p class="text-gray-500">No visits found</p>';

            // Habits
            document.getElementById('habits-list').innerHTML = data.habits.map(h => `
                <div class="bg-gray-700 rounded-lg p-3">
                    <div class="text-sm text-gray-200">${escapeHtml(h.content)}</div>
                    <div class="flex items-center gap-2 mt-2">
                        <div class="flex-1 bg-gray-600 h-1 rounded">
                            <div class="bg-green-500 h-1 rounded" style="width: ${h.confidence * 100}%"></div>
                        </div>
                        <span class="text-xs text-gray-400">${(h.confidence * 100).toFixed(0)}%</span>
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No habits found</p>';
        }

        function triggerContext(context) {
            ws.send(JSON.stringify({ type: 'context_search', context }));
        }

        function showContextResults(context, results) {
            document.getElementById('current-context').textContent = context;
            document.getElementById('context-results').classList.remove('hidden');

            document.getElementById('context-list').innerHTML = results.map(m => `
                <div class="bg-gray-700/50 rounded-lg p-3 border-l-4 border-violet-500">
                    <div class="text-sm text-gray-200">${escapeHtml(m.content)}</div>
                    <div class="text-xs text-gray-400 mt-1">${m.memory_type}</div>
                </div>
            `).join('') || '<p class="text-gray-500">No relevant memories</p>';
        }

        function getPriorityColor(priority) {
            return { high: 'border-red-500', medium: 'border-yellow-500', low: 'border-green-500' }[priority] || 'border-gray-500';
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
    logger.info(f"HTTP server running on port {port}")
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
    print("  PERSONAL ASSISTANT - WEB UI")
    print(f"{'='*60}")
    print(f"\n  Dashboard: http://localhost:{http_port}")
    print(f"  WebSocket: ws://localhost:{ws_port}")
    print(f"\n  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    async with websockets.serve(websocket_handler, "localhost", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Personal Assistant Web UI")
    parser.add_argument("--port", type=int, default=8122, help="HTTP port")
    parser.add_argument("--ws-port", type=int, default=8123, help="WebSocket port")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port, args.ws_port))
    except KeyboardInterrupt:
        print("\nShutting down...")
