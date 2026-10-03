"""
Fault-Injection WebSocket Proxy for Roundtable.

Forwards WebSocket traffic from --listen-port (default 8001) to
--target-port (default 8000) while allowing CLI-controlled fault
injection: latency and connection drops.

Edge case: when a drop is injected, both the client-side and
server-side connections are cleanly closed.

Usage:
    python ws4_eval/proxy.py [--listen-port 8001] [--target-port 8000]
                              [--latency-ms 0] [--drop-rate 0.0]

    --latency-ms N   Add N ms of latency to every forwarded message.
    --drop-rate F     Probability [0.0-1.0] of dropping a message and
                      closing both connections.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys

import websockets
import websockets.server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fault_proxy")


class FaultConfig:
    """Mutable fault injection configuration."""

    def __init__(self, latency_ms: float = 0.0, drop_rate: float = 0.0):
        self.latency_ms = latency_ms
        self.drop_rate = drop_rate


async def _forward(
    source: websockets.WebSocketCommonProtocol,
    dest: websockets.WebSocketCommonProtocol,
    direction: str,
    config: FaultConfig,
    cancel_event: asyncio.Event,
) -> None:
    """Forward messages from source to dest, applying faults."""
    try:
        async for message in source:
            if cancel_event.is_set():
                break

            # Check for drop
            if config.drop_rate > 0 and random.random() < config.drop_rate:
                logger.warning(
                    "[%s] DROP injected — closing both connections", direction
                )
                cancel_event.set()
                # Close both ends
                await _safe_close(source)
                await _safe_close(dest)
                return

            # Inject latency
            if config.latency_ms > 0:
                await asyncio.sleep(config.latency_ms / 1000.0)

            # Forward
            await dest.send(message)
            msg_desc = (
                f"{len(message)} bytes"
                if isinstance(message, bytes)
                else f"{len(message)} chars"
            )
            logger.debug("[%s] Forwarded %s", direction, msg_desc)
    except websockets.exceptions.ConnectionClosed:
        logger.info("[%s] Connection closed", direction)
        cancel_event.set()
    except Exception:
        logger.exception("[%s] Unexpected error in forwarder", direction)
        cancel_event.set()


async def _safe_close(ws: websockets.WebSocketCommonProtocol) -> None:
    """Close a WebSocket connection, ignoring errors."""
    try:
        await ws.close()
    except Exception:
        pass


async def handle_proxy_connection(
    client_ws: websockets.server.WebSocketServerProtocol,
    target_host: str,
    target_port: int,
    config: FaultConfig,
) -> None:
    """Handle a proxied connection: connect to target, forward both ways."""
    target_url = f"ws://{target_host}:{target_port}"
    remote = client_ws.remote_address
    logger.info("Proxying %s -> %s", remote, target_url)

    try:
        async with websockets.connect(target_url) as server_ws:
            cancel_event = asyncio.Event()

            client_to_server = asyncio.create_task(
                _forward(client_ws, server_ws, "client->server", config, cancel_event)
            )
            server_to_client = asyncio.create_task(
                _forward(server_ws, client_ws, "server->client", config, cancel_event)
            )

            # Wait for either direction to finish
            done, pending = await asyncio.wait(
                [client_to_server, server_to_client],
                return_when=asyncio.FIRST_COMPLETED,
            )
            cancel_event.set()

            # Cancel and await pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Ensure both sides are closed
            await _safe_close(server_ws)
    except (ConnectionRefusedError, OSError) as exc:
        logger.error("Cannot connect to target %s: %s", target_url, exc)
        await _safe_close(client_ws)
    except Exception:
        logger.exception("Error in proxy connection")
        await _safe_close(client_ws)

    logger.info("Proxy session ended for %s", remote)


async def main(
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    config: FaultConfig,
) -> None:
    """Start the fault-injection proxy."""
    logger.info(
        "Fault proxy: ws://%s:%d -> ws://%s:%d  "
        "(latency=%dms, drop_rate=%.2f)",
        listen_host,
        listen_port,
        target_host,
        target_port,
        config.latency_ms,
        config.drop_rate,
    )

    async def handler(ws: websockets.server.WebSocketServerProtocol) -> None:
        await handle_proxy_connection(ws, target_host, target_port, config)

    async with websockets.serve(handler, listen_host, listen_port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roundtable Fault Proxy")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=8001)
    parser.add_argument("--target-host", default="localhost")
    parser.add_argument("--target-port", type=int, default=8000)
    parser.add_argument(
        "--latency-ms", type=float, default=0.0,
        help="Added latency per message (ms)",
    )
    parser.add_argument(
        "--drop-rate", type=float, default=0.0,
        help="Probability of dropping a message and closing connection (0.0-1.0)",
    )
    args = parser.parse_args()

    config = FaultConfig(latency_ms=args.latency_ms, drop_rate=args.drop_rate)
    asyncio.run(
        main(args.listen_host, args.listen_port, args.target_host, args.target_port, config)
    )
