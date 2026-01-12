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

    # Memory type counts
    semantic_count = 0
    episodic_count = 0
    working_count = 0

    for mem in memories_cache.values():
        topics = mem.get("topics", [])
        mem_type = mem.get("memory_type")
        metadata = mem.get("metadata", {})

        # Count by type
        if mem_type == "semantic":
            semantic_count += 1
        elif mem_type == "episodic":
            episodic_count += 1
        elif mem_type == "working":
            working_count += 1

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

    # Build day timeline from location history
    timeline_events = []
    for loc in location_history[:15]:
        metadata = loc.get("metadata", {})
        timeline_events.append({
            "content": loc["content"],
            "location": metadata.get("location", "Unknown"),
            "duration": metadata.get("duration_mins", 0),
            "time": metadata.get("time", ""),
        })

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "memory_types": {
            "semantic": semantic_count,
            "episodic": episodic_count,
            "working": working_count,
        },
        "preferences": [{"content": p["content"], "topics": p.get("topics", []), "confidence": p.get("confidence", 0)} for p in preferences],
        "reminders": [{"content": r["content"], "context": r.get("context", ""), "priority": r.get("metadata", {}).get("priority", "medium"), "topics": r.get("topics", [])} for r in reminders],
        "location_history": timeline_events,
        "habits": [{"content": h["content"], "confidence": h.get("confidence", 0), "topics": h.get("topics", [])} for h in habits],
        "preference_count": len(preferences),
        "reminder_count": len(reminders),
        "habit_count": len(habits),
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
    <meta name="description" content="Personal Assistant Semantic Memory Dashboard">
    <title>Personal Assistant - TesseraiDB</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 10px rgba(139, 92, 246, 0.3); }
            50% { box-shadow: 0 0 25px rgba(139, 92, 246, 0.6); }
        }
        @keyframes slide-in {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes context-pop {
            0% { transform: scale(0.95); opacity: 0; }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); opacity: 1; }
        }
        @keyframes timeline-dot {
            0% { transform: scale(1); }
            50% { transform: scale(1.3); }
            100% { transform: scale(1); }
        }
        .pulse-glow { animation: pulse-glow 2s ease-in-out infinite; }
        .slide-in { animation: slide-in 0.4s ease-out forwards; }
        .context-pop { animation: context-pop 0.3s ease-out forwards; }
        .timeline-active .timeline-dot { animation: timeline-dot 1s ease-in-out infinite; }
        .card-hover { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .card-hover:hover { transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,0.3); }
        .gradient-bg {
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 50%, #1e3a5f 100%);
        }
        .glass-card {
            background: rgba(30, 27, 75, 0.5);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(139, 92, 246, 0.2);
        }
        .context-btn {
            transition: all 0.2s;
        }
        .context-btn:hover {
            transform: scale(1.05);
        }
        .context-btn.active {
            transform: scale(0.98);
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.3);
        }
        .timeline-line {
            background: linear-gradient(180deg, rgba(139, 92, 246, 0.8) 0%, rgba(59, 130, 246, 0.4) 100%);
        }
    </style>
</head>
<body class="gradient-bg text-white min-h-screen">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-violet-600 text-white px-4 py-2 rounded-lg z-50">
        Skip to main content
    </a>

    <main id="main-content" class="container mx-auto px-4 py-8 max-w-7xl">
        <!-- Header -->
        <header class="flex justify-between items-center mb-8">
            <div class="flex items-center gap-4">
                <div class="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center pulse-glow">
                    <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
                <div>
                    <h1 class="text-3xl font-bold bg-gradient-to-r from-violet-400 to-pink-400 bg-clip-text text-transparent">Personal Assistant</h1>
                    <p class="text-slate-400 mt-1">Context-Aware Memory Dashboard</p>
                </div>
            </div>
            <div class="flex items-center gap-4">
                <div id="connection-status" class="flex items-center gap-2 px-4 py-2 rounded-full text-sm glass-card" role="status" aria-live="polite">
                    <span class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" aria-hidden="true"></span>
                    <span>Connecting...</span>
                </div>
                <button onclick="refresh()" class="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 rounded-xl transition-all shadow-lg shadow-violet-500/25 font-medium" aria-label="Refresh dashboard data">
                    Refresh
                </button>
            </div>
        </header>

        <!-- Stats Cards -->
        <section aria-labelledby="stats-heading" class="mb-8">
            <h2 id="stats-heading" class="sr-only">Memory Statistics</h2>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-white" id="stat-total">-</span>
                        <div class="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Total Memories</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-purple-400" id="stat-preferences">-</span>
                        <div class="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Preferences</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-orange-400" id="stat-reminders">-</span>
                        <div class="w-12 h-12 rounded-xl bg-orange-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Active Reminders</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-green-400" id="stat-habits">-</span>
                        <div class="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Learned Habits</p>
                </article>
            </div>
        </section>

        <!-- Context Simulator & Chart Row -->
        <section aria-labelledby="context-heading" class="grid lg:grid-cols-3 gap-6 mb-8">
            <div class="lg:col-span-2 glass-card rounded-2xl p-6">
                <h2 id="context-heading" class="text-xl font-semibold mb-2 flex items-center gap-2">
                    <svg class="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Context Simulator
                </h2>
                <p class="text-slate-400 text-sm mb-5">Tap a location to see relevant memories and reminders</p>
                <div class="flex flex-wrap gap-3" role="group" aria-label="Location context triggers">
                    <button onclick="triggerContext('grocery store')" class="context-btn px-5 py-3 bg-green-600/20 text-green-400 border border-green-500/30 rounded-xl hover:bg-green-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                        Grocery Store
                    </button>
                    <button onclick="triggerContext('coffee shop')" class="context-btn px-5 py-3 bg-amber-600/20 text-amber-400 border border-amber-500/30 rounded-xl hover:bg-amber-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" /></svg>
                        Coffee Shop
                    </button>
                    <button onclick="triggerContext('office')" class="context-btn px-5 py-3 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-xl hover:bg-blue-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                        Office
                    </button>
                    <button onclick="triggerContext('gym')" class="context-btn px-5 py-3 bg-pink-600/20 text-pink-400 border border-pink-500/30 rounded-xl hover:bg-pink-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        Gym
                    </button>
                    <button onclick="triggerContext('restaurant')" class="context-btn px-5 py-3 bg-rose-600/20 text-rose-400 border border-rose-500/30 rounded-xl hover:bg-rose-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                        Restaurant
                    </button>
                    <button onclick="triggerContext('home')" class="context-btn px-5 py-3 bg-cyan-600/20 text-cyan-400 border border-cyan-500/30 rounded-xl hover:bg-cyan-600/30 flex items-center gap-2 font-medium">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                        Home
                    </button>
                </div>

                <div id="context-results" class="mt-6 hidden" role="region" aria-live="polite" aria-label="Context search results">
                    <div class="flex items-center gap-2 mb-4">
                        <div class="w-3 h-3 rounded-full bg-violet-500 animate-pulse" aria-hidden="true"></div>
                        <h3 class="text-lg font-medium">Relevant at <span id="current-context" class="text-violet-400"></span></h3>
                    </div>
                    <div id="context-list" class="grid gap-3"></div>
                </div>
            </div>

            <!-- Memory Type Chart -->
            <div class="glass-card rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 text-slate-200">Memory Distribution</h3>
                <div class="h-48">
                    <canvas id="memoryChart" aria-label="Memory type distribution chart"></canvas>
                </div>
            </div>
        </section>

        <!-- Day Timeline & Preferences -->
        <section class="grid lg:grid-cols-2 gap-8 mb-8">
            <!-- Day Timeline -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="timeline-heading">
                <h2 id="timeline-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Location Timeline
                </h2>
                <div id="timeline-container" class="relative" role="list" aria-label="Location visit timeline">
                    <div class="absolute left-5 top-0 bottom-0 w-0.5 timeline-line" aria-hidden="true"></div>
                    <div id="timeline-events" class="space-y-4">
                        <p class="text-slate-500 ml-12">Loading timeline...</p>
                    </div>
                </div>
            </div>

            <!-- Preferences -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="preferences-heading">
                <h2 id="preferences-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                    User Preferences
                </h2>
                <div id="preferences-list" class="space-y-3" role="list">
                    <p class="text-slate-500">Loading preferences...</p>
                </div>
            </div>
        </section>

        <!-- Reminders & Habits -->
        <section class="grid lg:grid-cols-2 gap-8">
            <!-- Active Reminders -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="reminders-heading">
                <h2 id="reminders-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    Active Reminders
                </h2>
                <div id="reminders-list" class="space-y-3" role="list">
                    <p class="text-slate-500">Loading reminders...</p>
                </div>
            </div>

            <!-- Learned Habits -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="habits-heading">
                <h2 id="habits-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Learned Habits
                </h2>
                <div id="habits-list" class="space-y-3" role="list">
                    <p class="text-slate-500">Loading habits...</p>
                </div>
            </div>
        </section>
    </main>

    <script>
        let ws;
        let chart;
        const WS_PORT = """ + str(WS_PORT) + """;

        function connect() {
            ws = new WebSocket(`ws://localhost:${WS_PORT}`);

            ws.onopen = () => {
                const status = document.getElementById('connection-status');
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-400" aria-hidden="true"></span><span>Connected</span>';
            };

            ws.onclose = () => {
                const status = document.getElementById('connection-status');
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-400 animate-pulse" aria-hidden="true"></span><span>Disconnected</span>';
                setTimeout(connect, 3000);
            };

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    handleMessage(msg);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
        }

        function handleMessage(msg) {
            if (msg.type === 'init') {
                updateDashboard(msg.data);
                updateChart(msg.data);
            } else if (msg.type === 'context_results') {
                showContextResults(msg.context, msg.results);
            }
        }

        function updateDashboard(data) {
            document.getElementById('stat-total').textContent = data.total_memories;
            document.getElementById('stat-preferences').textContent = data.preference_count;
            document.getElementById('stat-reminders').textContent = data.reminder_count;
            document.getElementById('stat-habits').textContent = data.habit_count;

            // Timeline
            const timelineEl = document.getElementById('timeline-events');
            timelineEl.innerHTML = data.location_history.map((e, i) => `
                <div class="flex items-start gap-4 slide-in" style="animation-delay: ${i * 0.08}s" role="listitem">
                    <div class="relative z-10 w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0 shadow-lg timeline-dot">
                        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        </svg>
                    </div>
                    <div class="flex-1 bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-medium text-blue-300">${escapeHtml(e.location || 'Location')}</span>
                            <span class="text-xs text-slate-500">${e.duration ? e.duration + ' min' : ''}</span>
                        </div>
                        <p class="text-sm text-slate-300">${escapeHtml(e.content)}</p>
                    </div>
                </div>
            `).join('') || '<p class="text-slate-500 ml-12">No location history</p>';

            // Preferences
            document.getElementById('preferences-list').innerHTML = data.preferences.map((p, i) => `
                <article class="slide-in bg-slate-800/40 rounded-xl p-4 border border-purple-500/20 hover:border-purple-500/40 transition-all" style="animation-delay: ${i * 0.05}s" role="listitem">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                            <svg class="w-4 h-4 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="flex-1">
                            <p class="text-sm text-slate-200">${escapeHtml(p.content)}</p>
                            <div class="flex gap-1.5 mt-2">
                                ${p.topics.slice(0,3).map(t => `<span class="text-xs px-2 py-0.5 bg-purple-900/40 text-purple-300 rounded-md">${escapeHtml(t)}</span>`).join('')}
                            </div>
                        </div>
                    </div>
                </article>
            `).join('') || '<p class="text-slate-500">No preferences found</p>';

            // Reminders
            document.getElementById('reminders-list').innerHTML = data.reminders.map((r, i) => `
                <article class="slide-in bg-slate-800/40 rounded-xl p-4 border-l-4 ${getPriorityColor(r.priority)}" style="animation-delay: ${i * 0.05}s" role="listitem">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-lg ${getPriorityBg(r.priority)} flex items-center justify-center flex-shrink-0" aria-hidden="true">
                            <svg class="w-4 h-4 ${getPriorityText(r.priority)}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                        <div class="flex-1">
                            <p class="text-sm text-slate-200 font-medium">${escapeHtml(r.content)}</p>
                            ${r.context ? `<p class="text-xs text-slate-400 mt-1">${escapeHtml(r.context)}</p>` : ''}
                            <div class="flex items-center gap-2 mt-2">
                                <span class="text-xs px-2 py-0.5 rounded ${getPriorityBadge(r.priority)}">${r.priority}</span>
                            </div>
                        </div>
                    </div>
                </article>
            `).join('') || '<p class="text-slate-500">No reminders found</p>';

            // Habits
            document.getElementById('habits-list').innerHTML = data.habits.map((h, i) => `
                <article class="slide-in bg-slate-800/40 rounded-xl p-4 border border-green-500/20 hover:border-green-500/40 transition-all" style="animation-delay: ${i * 0.05}s" role="listitem">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                            <svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <div class="flex-1">
                            <p class="text-sm text-slate-200">${escapeHtml(h.content)}</p>
                            <div class="flex items-center gap-2 mt-3">
                                <div class="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                    <div class="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full transition-all duration-500" style="width: ${h.confidence * 100}%"></div>
                                </div>
                                <span class="text-xs font-medium text-green-400">${(h.confidence * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                    </div>
                </article>
            `).join('') || '<p class="text-slate-500">No habits learned yet</p>';
        }

        function updateChart(data) {
            const ctx = document.getElementById('memoryChart').getContext('2d');
            if (chart) chart.destroy();

            chart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Semantic', 'Episodic', 'Working'],
                    datasets: [{
                        data: [data.memory_types.semantic, data.memory_types.episodic, data.memory_types.working],
                        backgroundColor: ['rgba(168, 85, 247, 0.8)', 'rgba(59, 130, 246, 0.8)', 'rgba(34, 197, 94, 0.8)'],
                        borderColor: ['rgba(168, 85, 247, 1)', 'rgba(59, 130, 246, 1)', 'rgba(34, 197, 94, 1)'],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 15, usePointStyle: true } }
                    },
                    cutout: '65%'
                }
            });
        }

        function triggerContext(context) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'context_search', context }));
            }
        }

        function showContextResults(context, results) {
            document.getElementById('current-context').textContent = context;
            const container = document.getElementById('context-results');
            container.classList.remove('hidden');

            document.getElementById('context-list').innerHTML = results.map((m, i) => `
                <article class="context-pop bg-slate-800/60 rounded-xl p-4 border-l-4 border-violet-500" style="animation-delay: ${i * 0.05}s">
                    <div class="flex items-start justify-between mb-2">
                        <span class="text-xs px-2 py-1 rounded-lg bg-violet-500/20 text-violet-300 border border-violet-500/30">${m.memory_type}</span>
                        ${m.confidence ? `<span class="text-xs text-slate-400">${(m.confidence * 100).toFixed(0)}%</span>` : ''}
                    </div>
                    <p class="text-sm text-slate-200">${escapeHtml(m.content)}</p>
                </article>
            `).join('') || '<p class="text-slate-500">No relevant memories for this context</p>';
        }

        function getPriorityColor(priority) {
            return { high: 'border-red-500', medium: 'border-yellow-500', low: 'border-green-500' }[priority] || 'border-slate-500';
        }

        function getPriorityBg(priority) {
            return { high: 'bg-red-500/20', medium: 'bg-yellow-500/20', low: 'bg-green-500/20' }[priority] || 'bg-slate-500/20';
        }

        function getPriorityText(priority) {
            return { high: 'text-red-400', medium: 'text-yellow-400', low: 'text-green-400' }[priority] || 'text-slate-400';
        }

        function getPriorityBadge(priority) {
            return { high: 'bg-red-500/20 text-red-300', medium: 'bg-yellow-500/20 text-yellow-300', low: 'bg-green-500/20 text-green-300' }[priority] || 'bg-slate-500/20 text-slate-300';
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function refresh() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'refresh' }));
            }
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
