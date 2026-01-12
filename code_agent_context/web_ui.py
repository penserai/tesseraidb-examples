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
    procedural_count = sum(1 for m in memories_cache.values() if m.get("memory_type") == "procedural")

    # Get patterns (high confidence semantic memories)
    patterns = [m for m in memories_cache.values()
                if m.get("memory_type") == "semantic" and m.get("confidence", 0) >= 0.85]

    # Get recent sessions with timeline data
    recent_sessions = []
    for session_id, mems in sessions_cache.items():
        session_mem = next((m for m in mems if "Session Goal" in m.get("content", "")), None)
        # Sort mems by created_at if available
        sorted_mems = sorted(mems, key=lambda m: m.get("created_at", ""))

        steps = []
        for i, m in enumerate(sorted_mems):
            steps.append({
                "index": i,
                "content": m.get("content", "")[:80],
                "type": m.get("memory_type", "unknown"),
                "record_type": m.get("record_type", ""),
                "confidence": m.get("confidence", 0),
                "topics": m.get("topics", [])[:3],
            })

        if session_mem:
            recent_sessions.append({
                "id": session_id,
                "goal": session_mem.get("content", "")[:100],
                "step_count": len(mems),
                "topics": session_mem.get("topics", []),
                "steps": steps[:15],  # First 15 steps for timeline
            })

    # Get topic distribution
    topic_counts = {}
    for m in memories_cache.values():
        for topic in m.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]

    # Get confidence distribution
    confidences = [m.get("confidence", 0) for m in memories_cache.values() if m.get("confidence")]
    confidence_buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for c in confidences:
        if c < 0.2:
            confidence_buckets["0-20"] += 1
        elif c < 0.4:
            confidence_buckets["20-40"] += 1
        elif c < 0.6:
            confidence_buckets["40-60"] += 1
        elif c < 0.8:
            confidence_buckets["60-80"] += 1
        else:
            confidence_buckets["80-100"] += 1

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "semantic_count": semantic_count,
        "episodic_count": episodic_count,
        "working_count": working_count,
        "procedural_count": procedural_count,
        "pattern_count": len(patterns),
        "session_count": len(sessions_cache),
        "recent_sessions": recent_sessions[:5],
        "patterns": [{"content": p["content"][:150], "topics": p.get("topics", []), "confidence": p.get("confidence", 0)} for p in patterns[:10]],
        "top_topics": [{"name": t[0], "count": t[1]} for t in top_topics],
        "confidence_distribution": confidence_buckets,
        "memory_types": {
            "semantic": semantic_count,
            "episodic": episodic_count,
            "working": working_count,
            "procedural": procedural_count,
        }
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
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @keyframes pulse-ring {
            0% { transform: scale(0.8); opacity: 1; }
            100% { transform: scale(1.4); opacity: 0; }
        }
        @keyframes flow-right {
            0% { transform: translateX(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateX(100%); opacity: 0; }
        }
        @keyframes slide-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes glow {
            0%, 100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.5); }
            50% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.8); }
        }
        .pulse-ring::before {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 50%;
            border: 2px solid currentColor;
            animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        .timeline-flow {
            position: relative;
            overflow: hidden;
        }
        .timeline-flow::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            width: 30px;
            height: 3px;
            background: linear-gradient(90deg, transparent, #3b82f6, transparent);
            animation: flow-right 2s ease-in-out infinite;
        }
        .slide-up { animation: slide-up 0.5s ease-out forwards; }
        .glow { animation: glow 2s ease-in-out infinite; }
        .memory-card { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .memory-card:hover { transform: translateY(-4px) scale(1.02); }
        .gradient-border {
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }
        .chart-container { position: relative; height: 200px; }
        .reasoning-step {
            opacity: 0;
            animation: slide-up 0.4s ease-out forwards;
        }
        .reasoning-step:nth-child(1) { animation-delay: 0.1s; }
        .reasoning-step:nth-child(2) { animation-delay: 0.2s; }
        .reasoning-step:nth-child(3) { animation-delay: 0.3s; }
        .reasoning-step:nth-child(4) { animation-delay: 0.4s; }
        .reasoning-step:nth-child(5) { animation-delay: 0.5s; }
        .timeline-node {
            transition: all 0.3s;
        }
        .timeline-node:hover {
            transform: scale(1.3);
            z-index: 10;
        }
    </style>
</head>
<body class="bg-slate-950 text-white min-h-screen">
    <!-- Gradient background -->
    <div class="fixed inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 -z-10"></div>
    <div class="fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent -z-10"></div>

    <div class="container mx-auto px-4 py-8 max-w-7xl">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div class="flex items-center gap-4">
                <div class="relative w-12 h-12 bg-blue-500/20 rounded-xl flex items-center justify-center pulse-ring text-blue-400">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>
                <div>
                    <h1 class="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Code Agent Context</h1>
                    <p class="text-slate-400 mt-1">Semantic Memory Dashboard</p>
                </div>
            </div>
            <div class="flex items-center gap-4">
                <div id="connection-status" class="flex items-center gap-2 px-4 py-2 rounded-full text-sm bg-yellow-500/10 border border-yellow-500/30 text-yellow-400">
                    <span class="w-2 h-2 rounded-full bg-current animate-pulse"></span>
                    <span>Connecting...</span>
                </div>
                <button onclick="refresh()" class="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 rounded-xl transition-all shadow-lg shadow-blue-500/25 font-medium">
                    Refresh
                </button>
            </div>
        </div>

        <!-- Stats Row with Charts -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div class="gradient-border rounded-2xl p-5 backdrop-blur">
                <div class="flex items-center justify-between mb-3">
                    <div class="text-4xl font-bold text-white" id="stat-total">-</div>
                    <div class="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                        <svg class="w-5 h-5 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                    </div>
                </div>
                <div class="text-slate-400 text-sm">Total Memories</div>
            </div>

            <div class="gradient-border rounded-2xl p-5 backdrop-blur">
                <div class="flex items-center justify-between mb-3">
                    <div class="text-4xl font-bold text-purple-400" id="stat-semantic">-</div>
                    <div class="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                    </div>
                </div>
                <div class="text-slate-400 text-sm">Semantic (Knowledge)</div>
            </div>

            <div class="gradient-border rounded-2xl p-5 backdrop-blur">
                <div class="flex items-center justify-between mb-3">
                    <div class="text-4xl font-bold text-blue-400" id="stat-episodic">-</div>
                    <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                </div>
                <div class="text-slate-400 text-sm">Episodic (Events)</div>
            </div>

            <div class="gradient-border rounded-2xl p-5 backdrop-blur">
                <div class="flex items-center justify-between mb-3">
                    <div class="text-4xl font-bold text-green-400" id="stat-patterns">-</div>
                    <div class="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                        <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    </div>
                </div>
                <div class="text-slate-400 text-sm">High-Confidence Patterns</div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid lg:grid-cols-3 gap-6 mb-8">
            <!-- Memory Type Distribution -->
            <div class="gradient-border rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 text-slate-200">Memory Type Distribution</h3>
                <div class="chart-container">
                    <canvas id="memoryTypeChart"></canvas>
                </div>
            </div>

            <!-- Confidence Distribution -->
            <div class="gradient-border rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 text-slate-200">Confidence Distribution</h3>
                <div class="chart-container">
                    <canvas id="confidenceChart"></canvas>
                </div>
            </div>

            <!-- Top Topics -->
            <div class="gradient-border rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 text-slate-200">Top Topics</h3>
                <div class="chart-container">
                    <canvas id="topicsChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Search -->
        <div class="gradient-border rounded-2xl p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
                <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Semantic Search
            </h2>
            <div class="flex gap-4">
                <input type="text" id="search-input" placeholder="Search memories... (e.g., 'authentication errors jwt')"
                       class="flex-1 bg-slate-800/50 border border-slate-700 rounded-xl px-5 py-3.5 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all placeholder-slate-500">
                <button onclick="search()" class="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 rounded-xl transition-all font-medium shadow-lg shadow-purple-500/20">
                    Search
                </button>
            </div>
            <div id="search-results" class="mt-6 hidden">
                <h3 class="text-lg font-medium mb-4 text-slate-300">Results</h3>
                <div id="results-list" class="grid gap-3"></div>
            </div>
        </div>

        <!-- Sessions with Reasoning Timeline -->
        <div class="gradient-border rounded-2xl p-6 mb-8">
            <h2 class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Active Sessions & Reasoning Chains
            </h2>
            <div id="sessions-timeline" class="space-y-6">
                <p class="text-slate-500">Loading sessions...</p>
            </div>
        </div>

        <!-- Learned Patterns -->
        <div class="gradient-border rounded-2xl p-6">
            <h2 class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Learned Patterns
                <span class="text-sm font-normal text-slate-400 ml-2">(High-confidence semantic memories)</span>
            </h2>
            <div id="patterns-list" class="grid md:grid-cols-2 gap-4">
                <p class="text-slate-500">Loading patterns...</p>
            </div>
        </div>

        <!-- Session Detail Modal -->
        <div id="session-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden items-center justify-center z-50">
            <div class="gradient-border rounded-2xl p-6 max-w-3xl w-full mx-4 max-h-[85vh] overflow-y-auto">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-xl font-semibold" id="modal-title">Session Detail</h2>
                    <button onclick="closeModal()" class="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div id="modal-content"></div>
            </div>
        </div>
    </div>

    <script>
        let ws;
        let charts = {};
        const WS_PORT = """ + str(WS_PORT) + """;

        function connect() {
            ws = new WebSocket(`ws://localhost:${WS_PORT}`);

            ws.onopen = () => {
                const status = document.getElementById('connection-status');
                status.className = 'flex items-center gap-2 px-4 py-2 rounded-full text-sm bg-green-500/10 border border-green-500/30 text-green-400';
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-current"></span><span>Connected</span>';
            };

            ws.onclose = () => {
                const status = document.getElementById('connection-status');
                status.className = 'flex items-center gap-2 px-4 py-2 rounded-full text-sm bg-red-500/10 border border-red-500/30 text-red-400';
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-current animate-pulse"></span><span>Disconnected</span>';
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
                updateCharts(msg.data);
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

            // Sessions with timeline
            const sessionsList = document.getElementById('sessions-timeline');
            sessionsList.innerHTML = data.recent_sessions.map(s => `
                <div class="memory-card bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 cursor-pointer hover:border-blue-500/50" onclick="getSession('${s.id}')">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold">${s.step_count}</div>
                            <div>
                                <div class="font-medium text-blue-300">${s.id}</div>
                                <div class="text-sm text-slate-400">${escapeHtml(s.goal.substring(0, 60))}...</div>
                            </div>
                        </div>
                        <div class="flex gap-2">
                            ${s.topics.slice(0,2).map(t => `<span class="text-xs px-2 py-1 bg-blue-900/30 text-blue-300 rounded-lg border border-blue-500/20">${t}</span>`).join('')}
                        </div>
                    </div>

                    <!-- Reasoning Timeline -->
                    <div class="relative">
                        <div class="absolute left-0 right-0 top-1/2 h-0.5 bg-gradient-to-r from-blue-500/50 via-purple-500/50 to-green-500/50 timeline-flow"></div>
                        <div class="flex justify-between relative">
                            ${s.steps.slice(0, 8).map((step, i) => `
                                <div class="timeline-node flex flex-col items-center cursor-pointer group" title="${escapeHtml(step.content)}">
                                    <div class="w-4 h-4 rounded-full ${getStepColor(step.type)} border-2 border-slate-900 z-10 shadow-lg"></div>
                                    <div class="absolute top-6 hidden group-hover:block bg-slate-800 border border-slate-600 rounded-lg p-2 text-xs max-w-xs z-20 shadow-xl">
                                        <div class="font-medium text-${getStepTextColor(step.type)}">${step.type}</div>
                                        <div class="text-slate-300 mt-1">${escapeHtml(step.content)}</div>
                                    </div>
                                </div>
                            `).join('')}
                            ${s.steps.length > 8 ? `<div class="text-xs text-slate-500 self-center">+${s.steps.length - 8} more</div>` : ''}
                        </div>
                    </div>
                </div>
            `).join('') || '<p class="text-slate-500">No sessions found</p>';

            // Patterns
            const patternsList = document.getElementById('patterns-list');
            patternsList.innerHTML = data.patterns.map(p => `
                <div class="memory-card bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 hover:border-green-500/30">
                    <div class="flex items-start gap-3 mb-3">
                        <div class="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center flex-shrink-0">
                            <svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <div class="text-sm text-slate-200 leading-relaxed">${escapeHtml(p.content)}</div>
                    </div>
                    <div class="flex items-center justify-between mt-4">
                        <div class="flex gap-1.5">
                            ${p.topics.slice(0,3).map(t => `<span class="text-xs px-2 py-0.5 bg-purple-900/30 text-purple-300 rounded-md">${t}</span>`).join('')}
                        </div>
                        <div class="flex items-center gap-2">
                            <div class="w-20 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                <div class="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full" style="width: ${p.confidence * 100}%"></div>
                            </div>
                            <span class="text-xs font-medium text-green-400">${(p.confidence * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                </div>
            `).join('') || '<p class="text-slate-500">No patterns found</p>';
        }

        function updateCharts(data) {
            // Destroy existing charts
            Object.values(charts).forEach(chart => chart.destroy());
            charts = {};

            // Memory Type Doughnut Chart
            const typeCtx = document.getElementById('memoryTypeChart').getContext('2d');
            charts.memoryType = new Chart(typeCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Semantic', 'Episodic', 'Working', 'Procedural'],
                    datasets: [{
                        data: [data.memory_types.semantic, data.memory_types.episodic, data.memory_types.working, data.memory_types.procedural],
                        backgroundColor: ['rgba(168, 85, 247, 0.8)', 'rgba(59, 130, 246, 0.8)', 'rgba(34, 197, 94, 0.8)', 'rgba(249, 115, 22, 0.8)'],
                        borderColor: ['rgba(168, 85, 247, 1)', 'rgba(59, 130, 246, 1)', 'rgba(34, 197, 94, 1)', 'rgba(249, 115, 22, 1)'],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 10, usePointStyle: true, pointStyle: 'circle' } }
                    },
                    cutout: '60%'
                }
            });

            // Confidence Bar Chart
            const confCtx = document.getElementById('confidenceChart').getContext('2d');
            const confData = data.confidence_distribution;
            charts.confidence = new Chart(confCtx, {
                type: 'bar',
                data: {
                    labels: ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'],
                    datasets: [{
                        data: [confData['0-20'], confData['20-40'], confData['40-60'], confData['60-80'], confData['80-100']],
                        backgroundColor: ['rgba(239, 68, 68, 0.7)', 'rgba(249, 115, 22, 0.7)', 'rgba(234, 179, 8, 0.7)', 'rgba(34, 197, 94, 0.7)', 'rgba(16, 185, 129, 0.7)'],
                        borderColor: ['rgba(239, 68, 68, 1)', 'rgba(249, 115, 22, 1)', 'rgba(234, 179, 8, 1)', 'rgba(34, 197, 94, 1)', 'rgba(16, 185, 129, 1)'],
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#64748b' } },
                        y: { grid: { color: 'rgba(100, 116, 139, 0.2)' }, ticks: { color: '#64748b' } }
                    }
                }
            });

            // Topics Horizontal Bar Chart
            const topicsCtx = document.getElementById('topicsChart').getContext('2d');
            charts.topics = new Chart(topicsCtx, {
                type: 'bar',
                data: {
                    labels: data.top_topics.slice(0, 6).map(t => t.name),
                    datasets: [{
                        data: data.top_topics.slice(0, 6).map(t => t.count),
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: 'rgba(100, 116, 139, 0.2)' }, ticks: { color: '#64748b' } },
                        y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        function getStepColor(type) {
            const colors = { 'semantic': 'bg-purple-500', 'episodic': 'bg-blue-500', 'working': 'bg-green-500', 'procedural': 'bg-orange-500' };
            return colors[type] || 'bg-slate-500';
        }

        function getStepTextColor(type) {
            const colors = { 'semantic': 'purple-400', 'episodic': 'blue-400', 'working': 'green-400', 'procedural': 'orange-400' };
            return colors[type] || 'slate-400';
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
            list.innerHTML = results.map((m, i) => `
                <div class="memory-card slide-up bg-slate-800/50 rounded-xl p-4 border border-slate-700/50" style="animation-delay: ${i * 0.05}s">
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-xs px-2.5 py-1 rounded-lg font-medium ${getTypeBadgeClass(m.memory_type)}">${m.memory_type}</span>
                        <span class="text-xs text-slate-400">${m.confidence ? (m.confidence * 100).toFixed(0) + '%' : ''}</span>
                    </div>
                    <div class="text-sm text-slate-200 leading-relaxed">${escapeHtml(m.content)}</div>
                    <div class="flex gap-1.5 mt-3">
                        ${(m.topics || []).slice(0,4).map(t => `<span class="text-xs px-2 py-0.5 bg-slate-700/50 text-slate-300 rounded">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p class="text-slate-500">No results found</p>';
        }

        function getTypeBadgeClass(type) {
            const classes = {
                'semantic': 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
                'episodic': 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
                'working': 'bg-green-500/20 text-green-300 border border-green-500/30',
                'procedural': 'bg-orange-500/20 text-orange-300 border border-orange-500/30'
            };
            return classes[type] || 'bg-slate-700 text-slate-300';
        }

        function getSession(sessionId) {
            ws.send(JSON.stringify({ type: 'get_session', session_id: sessionId }));
        }

        function showSessionDetail(data) {
            document.getElementById('modal-title').textContent = `Session: ${data.session_id}`;
            document.getElementById('modal-content').innerHTML = `
                <div class="space-y-4">
                    ${data.memories.map((m, i) => `
                        <div class="reasoning-step flex gap-4" style="animation-delay: ${i * 0.08}s">
                            <div class="flex flex-col items-center">
                                <div class="w-10 h-10 rounded-xl ${getTypeBadgeClass(m.memory_type)} flex items-center justify-center text-sm font-bold">${i + 1}</div>
                                ${i < data.memories.length - 1 ? '<div class="w-0.5 flex-1 bg-gradient-to-b from-blue-500/50 to-transparent mt-2"></div>' : ''}
                            </div>
                            <div class="flex-1 bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 mb-2">
                                <div class="flex items-center gap-2 mb-2">
                                    <span class="text-xs font-medium ${getTypeBadgeClass(m.memory_type)} px-2 py-0.5 rounded">${m.memory_type}</span>
                                    ${m.record_type ? `<span class="text-xs text-slate-500">${m.record_type}</span>` : ''}
                                </div>
                                <div class="text-sm text-slate-200 leading-relaxed">${escapeHtml(m.content)}</div>
                                <div class="text-xs text-slate-500 mt-2">${m.confidence ? (m.confidence * 100).toFixed(0) + '% confidence' : ''}</div>
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
