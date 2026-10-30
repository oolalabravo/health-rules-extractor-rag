import os
import re
import sys
import time
import asyncio
from typing import Optional, Dict, Any
import requests

# Windows UTF-8 console output guard
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
PROGRESS_PATH = os.path.join(BASE_DIR, "progress.md")
COLAB_CELL_ID = "2ZZKWkd_MzVj"
COLAB_MCP_EXE = r"C:\Users\intel\.local\bin\colab-mcp.exe"

# Load local .env
try:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
except ImportError:
    pass

def get_current_colab_url() -> Optional[str]:
    """Retrieves the current COLAB_API_URL from environment or .env file."""
    url = os.getenv("COLAB_API_URL")
    if url:
        return url.strip()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("COLAB_API_URL="):
                        return line.strip().split("=", 1)[1].strip()
        except Exception:
            pass
    return None

def check_colab_health(url: Optional[str] = None, timeout: float = 3.0) -> bool:
    """Checks if the Colab extraction server is healthy and responding."""
    target = url or get_current_colab_url()
    if not target or "ngrok-free.app" not in target and "trycloudflare.com" not in target:
        return False

    base_url = target.replace("/extract-rules", "").rstrip("/")
    health_url = f"{base_url}/health"
    try:
        res = requests.get(health_url, timeout=timeout)
        if res.status_code == 200:
            data = res.json()
            return data.get("status") == "healthy"
    except Exception:
        pass
    return False

def sync_url_to_env(new_url: str) -> None:
    """Safely writes the new Colab URL to .env and updates current process environment."""
    os.environ["COLAB_API_URL"] = new_url
    lines = []
    found = False

    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    new_lines = []
    for line in lines:
        if line.strip().startswith("COLAB_API_URL="):
            new_lines.append(f"COLAB_API_URL={new_url}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"COLAB_API_URL={new_url}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"💾 Updated .env with active COLAB_API_URL: {new_url}")

async def run_mcp_cell_execution(cell_id: str = COLAB_CELL_ID) -> str:
    """Connects to colab-mcp via stdio, runs Cell 0, and extracts the tunnel endpoint."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not os.path.exists(COLAB_MCP_EXE):
        raise FileNotFoundError(f"Colab MCP executable not found at: {COLAB_MCP_EXE}")

    server_params = StdioServerParameters(command=COLAB_MCP_EXE, args=[])

    print("🔌 Connecting to Colab MCP bridge...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            tool_names = [t.name for t in tools_resp.tools]

            # If browser connection isn't open yet, unlock it
            if "run_code_cell" not in tool_names:
                print("🌐 Connecting to Google Colab browser tab...")
                await session.call_tool("open_colab_browser_connection", {})
                await asyncio.sleep(2)
                tools_resp = await session.list_tools()
                tool_names = [t.name for t in tools_resp.tools]

            if "run_code_cell" not in tool_names:
                raise RuntimeError("Colab browser connection is not active. Please ensure your Colab notebook tab is open.")

            print(f"▶️ Triggering execution of Colab Cell ({cell_id})...")
            result = await session.call_tool("run_code_cell", {"cellId": cell_id})

            output_text = ""
            if hasattr(result, "content") and result.content:
                for item in result.content:
                    if hasattr(item, "text"):
                        output_text += item.text + "\n"
            else:
                output_text = str(result)

            # Match machine-readable marker: COLAB_TUNNEL_ENDPOINT = https://...
            match = re.search(r"COLAB_TUNNEL_ENDPOINT\s*=\s*(https://[^\s]+)", output_text)
            if match:
                return match.group(1).strip()

            # Generic fallback regex for ngrok or cloudflare tunnels
            match_generic = re.search(r"(https://[a-zA-Z0-9-]+\.(?:ngrok-free\.app|trycloudflare\.com)(?:/extract-rules)?)", output_text)
            if match_generic:
                url = match_generic.group(1).strip()
                if not url.endswith("/extract-rules"):
                    url = f"{url}/extract-rules"
                return url

            raise RuntimeError(f"Could not parse tunnel URL from Colab execution output:\n{output_text[:500]}")

def trigger_colab_cell_execution(cell_id: str = COLAB_CELL_ID) -> str:
    """Synchronous wrapper for MCP cell execution."""
    return asyncio.run(run_mcp_cell_execution(cell_id))

def ensure_colab_ready(force_restart: bool = False) -> str:
    """
    Guarantees an active, healthy Colab extractor URL.
    - If current URL is already healthy -> returns it in ~50ms.
    - If offline -> automatically runs Cell 0 in Colab, discovers URL, saves to .env, and verifies health.
    """
    current_url = get_current_colab_url()
    if not force_restart and current_url and check_colab_health(current_url):
        print(f"⚡ Active Colab extractor detected at: {current_url}")
        return current_url

    print("\n" + "=" * 60)
    print("📡 Colab extraction server is not running or URL is expired.")
    print("🚀 Triggering Google Colab Cell 0 automatically via MCP...")
    print("=" * 60)

    try:
        new_url = trigger_colab_cell_execution(COLAB_CELL_ID)
        sync_url_to_env(new_url)

        # Verify new server health
        print("⏳ Verifying server health...")
        for _ in range(10):
            if check_colab_health(new_url, timeout=2.0):
                print(f"✅ Colab extractor is active and verified healthy at: {new_url}\n")
                return new_url
            time.sleep(1)

        print(f"⚠️ Health check did not respond yet, but URL obtained: {new_url}\n")
        return new_url

    except Exception as e:
        print(f"❌ Failed to automatically trigger Colab: {e}")
        print("💡 Ensure your Colab notebook tab is open and connected to runtime.")
        if current_url:
            print(f"Falling back to existing URL: {current_url}")
            return current_url
        raise

if __name__ == "__main__":
    url = ensure_colab_ready()
    print(f"Final Colab API Endpoint: {url}")
