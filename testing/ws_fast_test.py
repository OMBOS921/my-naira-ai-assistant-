"""Quick WebSocket test — sends 'open youtube' and prints response."""
import asyncio
import websockets

async def run_ws_test():
    uri = "ws://127.0.0.1:8000/ws"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        test_commands = [
            "open chrome",
            "open youtube",
            "open calculator",
            "open notepad",
        ]
        for cmd in test_commands:
            print(f"\n--- Sending: {cmd!r} ---")
            await ws.send(cmd)
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=15)
                print(f"Response: {resp}")
            except asyncio.TimeoutError:
                print("TIMEOUT — no response in 15s (Gemini was likely called)")

if __name__ == "__main__":
    asyncio.run(run_ws_test())
