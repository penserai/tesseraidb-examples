#!/usr/bin/env python3
"""
Code Agent Context Management - Interactive Web UI

A web dashboard for visualizing coding agent memory including:
- Session history and reasoning chains
- Semantic memory (learned patterns)
- Natural language search across all memories
- Memory statistics and analytics

Usage:
    python web_ui.py [--port 8120]

Then open http://localhost:8120 in your browser.

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
from datetime import datetime
from typing import Dict, Set
import html

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Configuration
AGENT_ID = "code-agent-vscode"
HTTP_PORT = 8120
WS_PORT = 8121

# Global state
client = None
connected_clients: Set = set()
memories_cache: Dict = {}
sessions_cache: Dict = {}


def load_memories():
    """Load memories from TesseraiDB."""
    global memories_cache, sessions_cache

    try:
        # Query all memories for the agent
        result = client.memory.query(
            agent_id=AGENT_ID,
            query={"limit": 500}
        )

        memories_cache = {}
        sessions_cache = {}

        for mem in result.memories:
            mem_dict = mem.model_dump() if hasattr(mem, 'model_dump') else mem
            memories_cache[mem_dict["id"]] = mem_dict

            # Group by session
            session_id = mem_dict.get("session_id")
            if session_id:
                if session_id not in sessions_cache:
                    sessions_cache[session_id] = []
                sessions_cache[session_id].append(mem_dict)

        logger.info(f"Loaded {len(memories_cache)} memories, {len(sessions_cache)} sessions")

    except Exception as e:
        logger.error(f"Failed to load memories: {e}")


def get_dashboard_data() -> dict:
    """Get dashboard summary data."""
    semantic_count = sum(1 for m in memories_cache.values() if m.get("memory_type") == "semantic")
    episodic_count = sum(1 for m in memories_cache.values() if m.get("memory_type") == "episodic")
    working_count = sum(1 for m in memories_cache.values() if m.get("memory_type") == "working")

    # Get patterns (high confidence semantic memories)
    patterns = [m for m in memories_cache.values()
                if m.get("memory_type") == "semantic" and m.get("confidence", 0) >= 0.85]

    # Get recent sessions
    recent_sessions = []
    for session_id, mems in sessions_cache.items():
        session_mem = next((m for m in mems if "Session Goal" in m.get("content", "")), None)
        if session_mem:
            recent_sessions.append({
                "id": session_id,
                "goal": session_mem.get("content", "")[:100],
                "step_count": len(mems),
                "topics": session_mem.get("topics", []),
            })

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "semantic_count": semantic_count,
        "episodic_count": episodic_count,
        "working_count": working_count,
        "pattern_count": len(patterns),
        "session_count": len(sessions_cache),
        "recent_sessions": recent_sessions[:5],
        "patterns": [{"content": p["content"][:150], "topics": p.get("topics", []), "confidence": p.get("confidence", 0)} for p in patterns[:10]],
    }


def search_memories(query: str) -> list:
    """Search memories using semantic search."""
    try:
        result = client.memory.query(
            agent_id=AGENT_ID,
            query={
                "query": query,
                "limit": 20,
                "min_relevance": 0.5,
            }
        )
        return [m.model_dump() if hasattr(m, 'model_dump') else m for m in result.memories]
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def get_session_detail(session_id: str) -> dict:
    """Get detailed session with reasoning chain."""
    mems = sessions_cache.get(session_id, [])
    # Sort by creation time if available
    mems.sort(key=lambda m: m.get("created_at", ""))

    return {
        "session_id": session_id,
        "memories": mems,
        "step_count": len(mems),
    }


async def websocket_handler(websocket):
    """Handle WebSocket connections."""
    connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        # Send initial data
        await websocket.send(json.dumps({
            "type": "init",
            "data": get_dashboard_data()
        }))

        async for message in websocket:
            try:
                msg = json.loads(message)
                msg_type = msg.get("type")

                if msg_type == "search":
                    query = msg.get("query", "")
                    results = search_memories(query)
                    await websocket.send(json.dumps({
                        "type": "search_results",
                        "query": query,
                        "results": results
                    }))

                elif msg_type == "get_session":
                    session_id = msg.get("session_id")
                    detail = get_session_detail(session_id)
                    await websocket.send(json.dumps({
                        "type": "session_detail",
                        "data": detail
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
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


# HTML Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Agent Context - TesseraiDB</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .memory-card { transition: all 0.2s; }
        .memory-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .confidence-bar { height: 4px; border-radius: 2px; }
        .fade-in { animation: fadeIn 0.3s ease-in; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold text-blue-400">Code Agent Context</h1>
                <p class="text-gray-400 mt-1">Semantic Memory Dashboard</p>
            </div>
            <div class="flex items-center gap-4">
                <span id="connection-status" class="px-3 py-1 rounded-full text-sm bg-yellow-500/20 text-yellow-400">Connecting...</span>
                <button onclick="refresh()" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition">Refresh</button>
            </div>
        </div>

        <!-- Stats Row -->
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-white" id="stat-total">-</div>
                <div class="text-gray-400 text-sm">Total Memories</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-purple-400" id="stat-semantic">-</div>
                <div class="text-gray-400 text-sm">Semantic</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-blue-400" id="stat-episodic">-</div>
                <div class="text-gray-400 text-sm">Episodic</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-green-400" id="stat-patterns">-</div>
                <div class="text-gray-400 text-sm">Patterns</div>
            </div>
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="text-3xl font-bold text-orange-400" id="stat-sessions">-</div>
                <div class="text-gray-400 text-sm">Sessions</div>
            </div>
        </div>

        <!-- Search -->
        <div class="bg-gray-800 rounded-xl p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4">Semantic Search</h2>
            <div class="flex gap-4">
                <input type="text" id="search-input" placeholder="Search memories... (e.g., 'authentication errors jwt')"
                       class="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500">
                <button onclick="search()" class="px-6 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg transition">Search</button>
            </div>
            <div id="search-results" class="mt-4 hidden">
                <h3 class="text-lg font-medium mb-3">Results</h3>
                <div id="results-list" class="space-y-3"></div>
            </div>
        </div>

        <!-- Main Content Grid -->
        <div class="grid md:grid-cols-2 gap-8">
            <!-- Sessions -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4">Recent Sessions</h2>
                <div id="sessions-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>

            <!-- Patterns -->
            <div class="bg-gray-800 rounded-xl p-6">
                <h2 class="text-xl font-semibold mb-4">Learned Patterns</h2>
                <div id="patterns-list" class="space-y-3">
                    <p class="text-gray-500">Loading...</p>
                </div>
            </div>
        </div>

        <!-- Session Detail Modal -->
        <div id="session-modal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50">
            <div class="bg-gray-800 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold" id="modal-title">Session Detail</h2>
                    <button onclick="closeModal()" class="text-gray-400 hover:text-white">&times;</button>
                </div>
                <div id="modal-content"></div>
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
            } else if (msg.type === 'search_results') {
                showSearchResults(msg.results);
            } else if (msg.type === 'session_detail') {
                showSessionDetail(msg.data);
            }
        }

        function updateDashboard(data) {
            document.getElementById('stat-total').textContent = data.total_memories;
            document.getElementById('stat-semantic').textContent = data.semantic_count;
            document.getElementById('stat-episodic').textContent = data.episodic_count;
            document.getElementById('stat-patterns').textContent = data.pattern_count;
            document.getElementById('stat-sessions').textContent = data.session_count;

            // Sessions
            const sessionsList = document.getElementById('sessions-list');
            sessionsList.innerHTML = data.recent_sessions.map(s => `
                <div class="memory-card bg-gray-700 rounded-lg p-4 cursor-pointer" onclick="getSession('${s.id}')">
                    <div class="font-medium text-blue-300 mb-1">${s.id}</div>
                    <div class="text-sm text-gray-300 mb-2">${escapeHtml(s.goal)}</div>
                    <div class="flex gap-2">
                        <span class="text-xs px-2 py-1 bg-gray-600 rounded">${s.step_count} steps</span>
                        ${s.topics.slice(0,3).map(t => `<span class="text-xs px-2 py-1 bg-blue-900/50 text-blue-300 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No sessions found</p>';

            // Patterns
            const patternsList = document.getElementById('patterns-list');
            patternsList.innerHTML = data.patterns.map(p => `
                <div class="memory-card bg-gray-700 rounded-lg p-4">
                    <div class="text-sm text-gray-200 mb-2">${escapeHtml(p.content)}</div>
                    <div class="flex items-center gap-2">
                        <div class="flex-1 bg-gray-600 confidence-bar">
                            <div class="bg-green-500 confidence-bar" style="width: ${p.confidence * 100}%"></div>
                        </div>
                        <span class="text-xs text-gray-400">${(p.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="flex gap-1 mt-2">
                        ${p.topics.slice(0,4).map(t => `<span class="text-xs px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No patterns found</p>';
        }

        function search() {
            const query = document.getElementById('search-input').value;
            if (query.trim()) {
                ws.send(JSON.stringify({ type: 'search', query }));
            }
        }

        function showSearchResults(results) {
            const container = document.getElementById('search-results');
            const list = document.getElementById('results-list');

            container.classList.remove('hidden');
            list.innerHTML = results.map(m => `
                <div class="memory-card bg-gray-700 rounded-lg p-4 fade-in">
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs px-2 py-1 rounded ${getTypeColor(m.memory_type)}">${m.memory_type}</span>
                        <span class="text-xs text-gray-400">${m.confidence ? (m.confidence * 100).toFixed(0) + '%' : ''}</span>
                    </div>
                    <div class="text-sm text-gray-200">${escapeHtml(m.content)}</div>
                    <div class="flex gap-1 mt-2">
                        ${(m.topics || []).slice(0,4).map(t => `<span class="text-xs px-2 py-0.5 bg-gray-600 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p class="text-gray-500">No results found</p>';
        }

        function getSession(sessionId) {
            ws.send(JSON.stringify({ type: 'get_session', session_id: sessionId }));
        }

        function showSessionDetail(data) {
            document.getElementById('modal-title').textContent = `Session: ${data.session_id}`;
            document.getElementById('modal-content').innerHTML = `
                <div class="space-y-3">
                    ${data.memories.map((m, i) => `
                        <div class="flex gap-3">
                            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm">${i + 1}</div>
                            <div class="flex-1 bg-gray-700 rounded-lg p-3">
                                <div class="text-sm text-gray-200">${escapeHtml(m.content)}</div>
                                <div class="text-xs text-gray-500 mt-1">${m.record_type || m.memory_type} • ${m.confidence ? (m.confidence * 100).toFixed(0) + '% confidence' : ''}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            document.getElementById('session-modal').classList.remove('hidden');
            document.getElementById('session-modal').classList.add('flex');
        }

        function closeModal() {
            document.getElementById('session-modal').classList.add('hidden');
            document.getElementById('session-modal').classList.remove('flex');
        }

        function getTypeColor(type) {
            const colors = {
                'semantic': 'bg-purple-600',
                'episodic': 'bg-blue-600',
                'working': 'bg-green-600',
                'procedural': 'bg-orange-600'
            };
            return colors[type] || 'bg-gray-600';
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function refresh() {
            ws.send(JSON.stringify({ type: 'refresh' }));
        }

        // Enter key for search
        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') search();
        });

        // Modal close on outside click
        document.getElementById('session-modal').addEventListener('click', (e) => {
            if (e.target.id === 'session-modal') closeModal();
        });

        connect();
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving the dashboard."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def run_http_server(port: int):
    """Run the HTTP server."""
    server = HTTPServer(("", port), DashboardHandler)
    logger.info(f"HTTP server running on port {port}")
    server.serve_forever()


async def main(http_port: int, ws_port: int):
    """Main entry point."""
    global client, HTTP_PORT, WS_PORT

    HTTP_PORT = http_port
    WS_PORT = ws_port

    # Initialize client
    client = get_client()
    load_memories()

    # Start HTTP server in thread
    http_thread = threading.Thread(target=run_http_server, args=(http_port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print("  CODE AGENT CONTEXT - WEB UI")
    print(f"{'='*60}")
    print(f"\n  Dashboard: http://localhost:{http_port}")
    print(f"  WebSocket: ws://localhost:{ws_port}")
    print(f"\n  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    # Start WebSocket server
    async with websockets.serve(websocket_handler, "localhost", ws_port):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code Agent Context Web UI")
    parser.add_argument("--port", type=int, default=8120, help="HTTP port")
    parser.add_argument("--ws-port", type=int, default=8121, help="WebSocket port")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port, args.ws_port))
    except KeyboardInterrupt:
        print("\nShutting down...")
