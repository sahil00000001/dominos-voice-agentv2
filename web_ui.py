"""
web_ui.py — Web Dashboard for Domino's Voice Receptionist
==========================================================
FastAPI + WebSocket server broadcasting real-time JSON events to all
connected browser clients.  Tracks order state, complaints, latency
telemetry, and scenario detection in addition to the basic call flow.
"""

import asyncio
import json
import os
import re
import threading
import time
from datetime import datetime
from typing import Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

# ── Module-level singleton ─────────────────────────────────────────────────
_ui_instance: Optional["WebDominosUI"] = None


# ── Module-level helpers (imported by tools.py and ui.py) ─────────────────

def add_log(message: str) -> None:
    if _ui_instance is not None:
        _ui_instance._push_log(message)

def add_complaint(customer_name: str, complaint_type: str, text: str) -> None:
    if _ui_instance is not None:
        _ui_instance._push_complaint(customer_name, complaint_type, text)

def update_order(
    customer_name: str = None,
    order_items: list = None,
    delivery_address: str = None,
    order_total_inr: float = None,
    status: str = None,
    upsell_items: list = None,
    estimated_delivery_minutes: int = None,
) -> None:
    if _ui_instance is not None:
        _ui_instance._push_order_update(
            customer_name, order_items, delivery_address,
            order_total_inr, status, upsell_items, estimated_delivery_minutes,
        )

def set_scenario(scenario_name: str) -> None:
    if _ui_instance is not None:
        _ui_instance._push_scenario(scenario_name)

def record_latency(ms: float) -> None:
    if _ui_instance is not None:
        _ui_instance._push_latency(ms)


class WebDominosUI:
    def __init__(self, port: int = 8000) -> None:
        global _ui_instance
        _ui_instance = self

        import ui as _ui_mod
        _ui_mod._ui_instance = self  # type: ignore[attr-defined]

        self._port = port
        self._connections: Set[WebSocket] = set()
        self._server_loop: Optional[asyncio.AbstractEventLoop] = None

        self._current_state = "idle"
        self._stats = {
            "calls": 0, "orders": 0, "revenue": 0.0,
            "upsells": 0, "complaints": 0, "avg_latency_ms": 0.0,
        }
        self._messages: list = []
        self._bot_buf: str = ""
        self._log_lines: list = []
        self._complaints: list = []
        self._order_state: dict = {}
        self._latency_history: list = []
        self._current_scenario: str = ""
        self._turn_count: int = 0

        self._app = self._build_app()

    # ── FastAPI ───────────────────────────────────────────────────────────

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/")
        async def dashboard():
            html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
            with open(html_path, encoding="utf-8") as f:
                return HTMLResponse(f.read())

        @app.get("/api/stats")
        async def api_stats():
            return JSONResponse({
                "stats": self._stats,
                "order": self._order_state,
                "complaints": self._complaints,
                "latency_history": self._latency_history,
                "current_scenario": self._current_scenario,
                "turn_count": self._turn_count,
            })

        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._connections.add(websocket)
            try:
                await websocket.send_text(json.dumps({
                    "type": "init",
                    "state": self._current_state,
                    "stats": self._stats,
                    "messages": self._messages,
                    "bot_buf": self._bot_buf,
                    "log_lines": self._log_lines,
                    "complaints": self._complaints,
                    "order": self._order_state,
                    "scenario": self._current_scenario,
                    "latency_history": self._latency_history,
                    "turn_count": self._turn_count,
                }))
            except Exception:
                pass
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self._connections.discard(websocket)

        return app

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._server_loop = loop
            config = uvicorn.Config(self._app, host="0.0.0.0", port=self._port, log_level="error")
            server = uvicorn.Server(config)
            loop.run_until_complete(server.serve())

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        time.sleep(1.2)
        url = f"http://localhost:{self._port}"
        print(f"\n  🌐  Dashboard → {url}\n  Speak into your mic. Press Ctrl+C to end.\n")
        import webbrowser
        webbrowser.open(url)

    def stop(self) -> None:
        pass

    # ── State setters ──────────────────────────────────────────────────────

    def set_idle(self) -> None:
        self._current_state = "idle"
        self._emit({"type": "state", "state": "idle"})

    def set_listening(self) -> None:
        self._current_state = "listening"
        self._emit({"type": "state", "state": "listening"})

    def set_thinking(self) -> None:
        self._current_state = "thinking"
        self._turn_count += 1
        self._emit({"type": "state", "state": "thinking", "turn_count": self._turn_count})

    def set_speaking(self) -> None:
        self._current_state = "speaking"
        self._emit({"type": "state", "state": "speaking"})

    # ── Conversation ───────────────────────────────────────────────────────

    def add_user_message(self, text: str) -> None:
        ts = _ts()
        self._messages.append({"speaker": "user", "text": text, "time": ts})
        self._emit({"type": "user_msg", "text": text, "time": ts})

    def append_bot_text(self, text: str) -> None:
        self._bot_buf += text
        self._emit({"type": "bot_chunk", "text": text})

    def finalise_bot_message(self) -> None:
        ts = _ts()
        text = self._bot_buf.strip()
        if text:
            self._messages.append({"speaker": "bot", "text": text, "time": ts})
        self._bot_buf = ""
        self._emit({"type": "bot_done", "time": ts})

    # ── Order tracking ─────────────────────────────────────────────────────

    def _push_order_update(
        self, customer_name, order_items, delivery_address,
        order_total_inr, status, upsell_items, estimated_delivery_minutes,
    ) -> None:
        if customer_name is not None:
            self._order_state["customer_name"] = customer_name
        if order_items is not None:
            self._order_state["order_items"] = order_items
        if delivery_address is not None:
            self._order_state["delivery_address"] = delivery_address
        if order_total_inr is not None:
            self._order_state["order_total_inr"] = order_total_inr
        if status is not None:
            self._order_state["status"] = status
        if upsell_items is not None:
            existing = self._order_state.get("upsell_items", [])
            self._order_state["upsell_items"] = existing + upsell_items
        if estimated_delivery_minutes is not None:
            self._order_state["estimated_delivery_minutes"] = estimated_delivery_minutes

        self._emit({"type": "order_update", "order": {**self._order_state}, "time": _ts()})

    # ── Complaint tracking ─────────────────────────────────────────────────

    def _push_complaint(self, customer_name: str, complaint_type: str, text: str) -> None:
        ts = _ts()
        is_refund = complaint_type == "refund"
        entry = {
            "type": "complaint",
            "customer_name": customer_name,
            "complaint_type": complaint_type,
            "text": text,
            "is_refund": is_refund,
            "time": ts,
        }
        self._complaints.append(entry)
        self._stats["complaints"] += 1
        self._emit({**entry, "stats": {**self._stats}})

    # ── Scenario ───────────────────────────────────────────────────────────

    def _push_scenario(self, scenario_name: str) -> None:
        self._current_scenario = scenario_name
        self._emit({"type": "scenario", "name": scenario_name, "time": _ts()})

    # ── Latency ────────────────────────────────────────────────────────────

    def _push_latency(self, ms: float) -> None:
        self._latency_history.append(round(ms, 1))
        if len(self._latency_history) > 50:
            self._latency_history.pop(0)
        avg = sum(self._latency_history) / len(self._latency_history)
        self._stats["avg_latency_ms"] = round(avg, 1)
        self._emit({
            "type": "latency",
            "ms": round(ms, 1),
            "avg_ms": self._stats["avg_latency_ms"],
        })

    # ── Order log ──────────────────────────────────────────────────────────

    def _push_log(self, message: str) -> None:
        clean = re.sub(r"\[/?[^\]]*\]", "", message).strip()
        event_type = "default"
        if "ORDER CONFIRMED" in message:
            event_type = "confirmed"
            self._stats["orders"] += 1
            m = re.search(r"₹(\d+(?:\.\d+)?)", clean)
            if m:
                self._stats["revenue"] += float(m.group(1))
        elif "UPSELL ADDED" in message:
            event_type = "upsell"
            self._stats["upsells"] += 1
            m = re.search(r"₹(\d+(?:\.\d+)?)", clean)
            if m:
                self._stats["revenue"] += float(m.group(1))
        elif "ORDER FINALISED" in message:
            event_type = "finalised"

        entry = {
            "type": "order_event",
            "message": clean,
            "event_type": event_type,
            "time": _ts(),
            "stats": {**self._stats},
        }
        self._log_lines.append(entry)
        self._emit(entry)

    # ── Broadcast ──────────────────────────────────────────────────────────

    def _emit(self, event: dict) -> None:
        if not self._connections or self._server_loop is None:
            return
        data = json.dumps(event, ensure_ascii=False)

        async def _send():
            dead: Set[WebSocket] = set()
            for ws in list(self._connections):
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.add(ws)
            self._connections -= dead

        asyncio.run_coroutine_threadsafe(_send(), self._server_loop)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")
