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

    # Memory type counts
    semantic_count = 0
    episodic_count = 0
    procedural_count = 0

    # Aggregate execution stats by process and step
    step_stats = defaultdict(lambda: {"durations": [], "delays": 0, "total": 0})
    process_stats = defaultdict(lambda: {"total": 0, "delays": 0, "durations": []})

    for mem in memories_cache.values():
        topics = mem.get("topics", [])
        mem_type = mem.get("memory_type")
        record_type = mem.get("record_type")
        metadata = mem.get("metadata", {})

        # Count by type
        if mem_type == "semantic":
            semantic_count += 1
        elif mem_type == "episodic":
            episodic_count += 1
        elif mem_type == "procedural":
            procedural_count += 1

        if record_type == "procedure" and "process-definition" in topics:
            processes.append({
                "id": metadata.get("process_id", mem["id"]),
                "content": mem["content"][:100],
                "version": mem.get("version", 1),
                "supersedes": metadata.get("supersedes"),
            })
        elif "process-log" in topics and mem_type == "episodic":
            exec_entry = {
                "id": metadata.get("execution_id", ""),
                "process": metadata.get("process_id", ""),
                "step": metadata.get("step", ""),
                "duration": metadata.get("duration_hours", 0),
                "expected": metadata.get("expected_hours", 0),
                "is_delay": metadata.get("is_delay", False),
                "reason": metadata.get("reason", ""),
            }
            executions.append(exec_entry)

            # Aggregate stats
            key = f"{metadata.get('process_id', '')}-{metadata.get('step', '')}"
            step_stats[key]["durations"].append(metadata.get("duration_hours", 0))
            step_stats[key]["total"] += 1
            if metadata.get("is_delay"):
                step_stats[key]["delays"] += 1

            # Process-level stats
            proc_key = metadata.get("process_id", "unknown")
            process_stats[proc_key]["total"] += 1
            process_stats[proc_key]["durations"].append(metadata.get("duration_hours", 0))
            if metadata.get("is_delay"):
                process_stats[proc_key]["delays"] += 1

        elif "bottleneck" in topics and mem_type == "semantic":
            bottlenecks.append({
                "content": mem["content"][:150],
                "confidence": mem.get("confidence", 0),
                "evidence_count": metadata.get("evidence_count", 0),
                "step": metadata.get("step", ""),
                "process": metadata.get("process", ""),
            })
        elif "evolution" in topics and record_type == "procedure":
            evolutions.append({
                "content": mem["content"][:100],
                "change": metadata.get("change", ""),
                "reason": metadata.get("reason", ""),
                "supersedes": metadata.get("supersedes", ""),
            })

    # Calculate step averages for bar chart
    step_performance = []
    for key, stats in step_stats.items():
        if stats["durations"]:
            avg = sum(stats["durations"]) / len(stats["durations"])
            parts = key.rsplit("-", 1)
            process_id = parts[0] if len(parts) > 1 else key
            step = parts[1] if len(parts) > 1 else "unknown"
            delay_rate = (stats["delays"] / stats["total"] * 100) if stats["total"] > 0 else 0
            step_performance.append({
                "process": process_id,
                "step": step,
                "avg_hours": round(avg, 1),
                "delay_count": stats["delays"],
                "total_runs": stats["total"],
                "delay_rate": round(delay_rate, 1),
            })

    step_performance.sort(key=lambda x: x["avg_hours"], reverse=True)

    # Process summary for chart
    process_summary = []
    for proc_id, stats in process_stats.items():
        if stats["durations"]:
            avg = sum(stats["durations"]) / len(stats["durations"])
            delay_rate = (stats["delays"] / stats["total"] * 100) if stats["total"] > 0 else 0
            process_summary.append({
                "name": proc_id.replace("-v1", "").replace("-", " ").title(),
                "avg_hours": round(avg, 1),
                "total_runs": stats["total"],
                "delay_rate": round(delay_rate, 1),
            })

    # Recent executions for Gantt-like timeline
    recent_executions = []
    exec_groups = defaultdict(list)
    for e in executions[:50]:
        exec_groups[e["id"]].append(e)

    for exec_id, steps in list(exec_groups.items())[:8]:
        recent_executions.append({
            "id": exec_id,
            "process": steps[0]["process"] if steps else "",
            "steps": sorted(steps, key=lambda x: x.get("step", "")),
            "has_delay": any(s["is_delay"] for s in steps),
        })

    return {
        "agent_id": AGENT_ID,
        "total_memories": len(memories_cache),
        "memory_types": {
            "semantic": semantic_count,
            "episodic": episodic_count,
            "procedural": procedural_count,
        },
        "processes": processes,
        "executions": recent_executions,
        "bottlenecks": bottlenecks,
        "evolutions": evolutions,
        "step_performance": step_performance[:10],
        "process_summary": process_summary,
        "delay_count": sum(1 for e in executions if e["is_delay"]),
        "total_executions": len(executions),
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
    <meta name="description" content="Business Process Evolution Dashboard">
    <title>Process Evolution - TesseraiDB</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @keyframes pulse-warning {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        @keyframes slide-right {
            from { width: 0; opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes grow-bar {
            from { transform: scaleX(0); }
            to { transform: scaleX(1); }
        }
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .pulse-warning { animation: pulse-warning 1.5s ease-in-out infinite; }
        .slide-right { animation: slide-right 0.6s ease-out forwards; }
        .grow-bar { animation: grow-bar 0.8s ease-out forwards; transform-origin: left; }
        .fade-in-up { animation: fade-in-up 0.4s ease-out forwards; }
        .card-hover { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .card-hover:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.25); }
        .gradient-bg {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f4c3a 100%);
        }
        .glass-card {
            background: rgba(15, 23, 42, 0.6);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        .gantt-bar {
            transition: all 0.3s;
        }
        .gantt-bar:hover {
            transform: scaleY(1.2);
            z-index: 10;
        }
        .bottleneck-glow {
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
        }
        .evolution-line {
            background: linear-gradient(180deg, rgba(16, 185, 129, 0.8) 0%, rgba(16, 185, 129, 0.2) 100%);
        }
    </style>
</head>
<body class="gradient-bg text-white min-h-screen">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-emerald-600 text-white px-4 py-2 rounded-lg z-50">
        Skip to main content
    </a>

    <main id="main-content" class="container mx-auto px-4 py-8 max-w-7xl">
        <!-- Header -->
        <header class="flex justify-between items-center mb-8">
            <div class="flex items-center gap-4">
                <div class="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                    <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                </div>
                <div>
                    <h1 class="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">Process Evolution</h1>
                    <p class="text-slate-400 mt-1">Business Process Intelligence Dashboard</p>
                </div>
            </div>
            <div class="flex items-center gap-4">
                <div id="connection-status" class="flex items-center gap-2 px-4 py-2 rounded-full text-sm glass-card" role="status" aria-live="polite">
                    <span class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" aria-hidden="true"></span>
                    <span>Connecting...</span>
                </div>
                <button onclick="refresh()" class="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-xl transition-all shadow-lg shadow-emerald-500/25 font-medium" aria-label="Refresh dashboard data">
                    Refresh
                </button>
            </div>
        </header>

        <!-- Stats Cards -->
        <section aria-labelledby="stats-heading" class="mb-8">
            <h2 id="stats-heading" class="sr-only">Process Statistics</h2>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-white" id="stat-total">-</span>
                        <div class="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Total Memories</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-blue-400" id="stat-processes">-</span>
                        <div class="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Process Definitions</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-red-400" id="stat-delays">-</span>
                        <div class="w-12 h-12 rounded-xl bg-red-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Delays Detected</p>
                </article>

                <article class="glass-card rounded-2xl p-5 card-hover">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-4xl font-bold text-green-400" id="stat-evolutions">-</span>
                        <div class="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center" aria-hidden="true">
                            <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                        </div>
                    </div>
                    <p class="text-slate-300 text-sm">Process Evolutions</p>
                </article>
            </div>
        </section>

        <!-- Charts Row -->
        <section aria-labelledby="charts-heading" class="grid lg:grid-cols-2 gap-6 mb-8">
            <h2 id="charts-heading" class="sr-only">Performance Charts</h2>

            <!-- Step Performance Chart -->
            <div class="glass-card rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 flex items-center gap-2">
                    <svg class="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Step Performance (Slowest Steps)
                </h3>
                <div class="h-64">
                    <canvas id="stepChart" aria-label="Step performance bar chart"></canvas>
                </div>
            </div>

            <!-- Process Delay Rate Chart -->
            <div class="glass-card rounded-2xl p-6">
                <h3 class="text-lg font-semibold mb-4 flex items-center gap-2">
                    <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Delay Rate by Process
                </h3>
                <div class="h-64">
                    <canvas id="delayChart" aria-label="Delay rate chart"></canvas>
                </div>
            </div>
        </section>

        <!-- Execution Timeline (Gantt-style) -->
        <section class="glass-card rounded-2xl p-6 mb-8" aria-labelledby="timeline-heading">
            <h2 id="timeline-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
                Recent Executions
                <span class="text-sm font-normal text-slate-400 ml-2">Gantt-style view of process steps</span>
            </h2>
            <div id="gantt-container" class="space-y-4" role="list" aria-label="Process execution timeline">
                <p class="text-slate-500">Loading executions...</p>
            </div>
        </section>

        <!-- Bottlenecks & Evolutions -->
        <section class="grid lg:grid-cols-2 gap-8">
            <!-- Bottleneck Analysis -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="bottlenecks-heading">
                <h2 id="bottlenecks-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Bottleneck Analysis
                </h2>
                <div id="bottlenecks-list" class="space-y-4" role="list">
                    <p class="text-slate-500">Loading bottlenecks...</p>
                </div>
            </div>

            <!-- Process Evolutions -->
            <div class="glass-card rounded-2xl p-6" aria-labelledby="evolutions-heading">
                <h2 id="evolutions-heading" class="text-xl font-semibold mb-6 flex items-center gap-2">
                    <svg class="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                    </svg>
                    Process Evolutions
                </h2>
                <div id="evolutions-list" class="relative" role="list">
                    <div class="absolute left-4 top-0 bottom-0 w-0.5 evolution-line" aria-hidden="true"></div>
                    <div id="evolutions-content" class="space-y-4 pl-10">
                        <p class="text-slate-500">Loading evolutions...</p>
                    </div>
                </div>
            </div>
        </section>
    </main>

    <script>
        let ws;
        let charts = {};
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
                    if (msg.type === 'init') {
                        updateDashboard(msg.data);
                        updateCharts(msg.data);
                    }
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
        }

        function updateDashboard(data) {
            document.getElementById('stat-total').textContent = data.total_memories;
            document.getElementById('stat-processes').textContent = data.processes.length;
            document.getElementById('stat-delays').textContent = data.delay_count;
            document.getElementById('stat-evolutions').textContent = data.evolutions.length;

            // Gantt-style executions
            const ganttEl = document.getElementById('gantt-container');
            ganttEl.innerHTML = data.executions.map((exec, i) => {
                const totalSteps = exec.steps.length;
                return `
                    <div class="fade-in-up" style="animation-delay: ${i * 0.1}s" role="listitem">
                        <div class="flex items-center gap-4 mb-2">
                            <div class="w-24 flex-shrink-0">
                                <span class="text-sm font-medium text-cyan-300">${escapeHtml(exec.id)}</span>
                            </div>
                            <div class="flex-1 flex items-center gap-1 h-10 bg-slate-800/50 rounded-lg overflow-hidden p-1">
                                ${exec.steps.map((step, j) => {
                                    const width = 100 / totalSteps;
                                    const isDelay = step.is_delay;
                                    const bgColor = isDelay ? 'bg-red-500' : 'bg-emerald-500';
                                    const hoverBg = isDelay ? 'hover:bg-red-400' : 'hover:bg-emerald-400';
                                    return `
                                        <div class="gantt-bar ${bgColor} ${hoverBg} h-full rounded cursor-pointer group relative"
                                             style="width: ${width}%; animation-delay: ${j * 0.05}s"
                                             title="${escapeHtml(step.step)}: ${step.duration}h">
                                            <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block bg-slate-900 border border-slate-600 rounded-lg p-2 text-xs min-w-max z-20">
                                                <div class="font-medium ${isDelay ? 'text-red-300' : 'text-emerald-300'}">${escapeHtml(step.step)}</div>
                                                <div class="text-slate-400 mt-1">${step.duration}h / ${step.expected}h expected</div>
                                                ${isDelay ? `<div class="text-red-400 mt-1">${escapeHtml(step.reason)}</div>` : ''}
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                            <div class="w-20 flex-shrink-0 text-right">
                                ${exec.has_delay ? '<span class="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded-lg">Delayed</span>' : '<span class="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded-lg">On time</span>'}
                            </div>
                        </div>
                    </div>
                `;
            }).join('') || '<p class="text-slate-500">No recent executions</p>';

            // Bottlenecks
            document.getElementById('bottlenecks-list').innerHTML = data.bottlenecks.map((b, i) => `
                <article class="fade-in-up bg-slate-800/40 rounded-xl p-4 border-l-4 border-red-500 ${b.confidence > 0.8 ? 'bottleneck-glow' : ''}" style="animation-delay: ${i * 0.08}s" role="listitem">
                    <div class="flex items-start gap-3">
                        <div class="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                            <svg class="w-5 h-5 text-red-400 ${b.confidence > 0.8 ? 'pulse-warning' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <div class="flex-1">
                            <p class="text-sm text-slate-200">${escapeHtml(b.content)}</p>
                            <div class="flex items-center gap-4 mt-3">
                                <div class="flex items-center gap-2">
                                    <div class="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                        <div class="h-full bg-gradient-to-r from-red-500 to-orange-400 rounded-full" style="width: ${b.confidence * 100}%"></div>
                                    </div>
                                    <span class="text-xs font-medium text-red-400">${(b.confidence * 100).toFixed(0)}%</span>
                                </div>
                                <span class="text-xs text-slate-500">${b.evidence_count} evidence</span>
                            </div>
                        </div>
                    </div>
                </article>
            `).join('') || '<p class="text-slate-500">No bottlenecks detected</p>';

            // Evolutions
            document.getElementById('evolutions-content').innerHTML = data.evolutions.map((e, i) => `
                <article class="fade-in-up relative" style="animation-delay: ${i * 0.1}s" role="listitem">
                    <div class="absolute -left-8 top-2 w-4 h-4 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 border-2 border-slate-900" aria-hidden="true"></div>
                    <div class="bg-slate-800/40 rounded-xl p-4 border border-emerald-500/20 hover:border-emerald-500/40 transition-all">
                        <div class="flex items-start justify-between gap-3 mb-2">
                            <span class="text-sm font-medium text-emerald-300">${escapeHtml(e.change || e.content)}</span>
                            <svg class="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <p class="text-xs text-slate-400">${escapeHtml(e.reason)}</p>
                        ${e.supersedes ? `<p class="text-xs text-emerald-400/70 mt-2">Evolved from: ${escapeHtml(e.supersedes)}</p>` : ''}
                    </div>
                </article>
            `).join('') || '<p class="text-slate-500">No evolutions yet</p>';
        }

        function updateCharts(data) {
            // Destroy existing charts
            Object.values(charts).forEach(chart => chart.destroy());
            charts = {};

            // Step Performance Chart
            const stepCtx = document.getElementById('stepChart').getContext('2d');
            const stepData = data.step_performance.slice(0, 6);
            charts.step = new Chart(stepCtx, {
                type: 'bar',
                data: {
                    labels: stepData.map(s => s.step.substring(0, 15)),
                    datasets: [{
                        label: 'Avg Hours',
                        data: stepData.map(s => s.avg_hours),
                        backgroundColor: stepData.map(s => s.delay_count > 0 ? 'rgba(239, 68, 68, 0.7)' : 'rgba(16, 185, 129, 0.7)'),
                        borderColor: stepData.map(s => s.delay_count > 0 ? 'rgba(239, 68, 68, 1)' : 'rgba(16, 185, 129, 1)'),
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
                        x: { grid: { color: 'rgba(100, 116, 139, 0.2)' }, ticks: { color: '#64748b' }, title: { display: true, text: 'Hours', color: '#94a3b8' } },
                        y: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                    }
                }
            });

            // Delay Rate Chart
            const delayCtx = document.getElementById('delayChart').getContext('2d');
            const procData = data.process_summary.slice(0, 5);
            charts.delay = new Chart(delayCtx, {
                type: 'doughnut',
                data: {
                    labels: procData.map(p => p.name),
                    datasets: [{
                        data: procData.map(p => p.delay_rate),
                        backgroundColor: [
                            'rgba(239, 68, 68, 0.8)',
                            'rgba(249, 115, 22, 0.8)',
                            'rgba(234, 179, 8, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(59, 130, 246, 0.8)'
                        ],
                        borderColor: [
                            'rgba(239, 68, 68, 1)',
                            'rgba(249, 115, 22, 1)',
                            'rgba(234, 179, 8, 1)',
                            'rgba(16, 185, 129, 1)',
                            'rgba(59, 130, 246, 1)'
                        ],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#94a3b8', padding: 12, usePointStyle: true } },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.label}: ${context.raw}% delay rate`;
                                }
                            }
                        }
                    },
                    cutout: '50%'
                }
            });
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
