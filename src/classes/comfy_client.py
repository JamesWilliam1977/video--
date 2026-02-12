"""
 @file
 @brief Small ComfyUI HTTP client for queue/poll/cancel operations.
"""

import json
import os
import ssl
import base64
import socket
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import quote, urlencode
from urllib.parse import urlparse

from classes.logger import log


class ComfyProgressSocket:
    """Minimal WebSocket client for ComfyUI /ws progress events."""

    def __init__(self, base_url, client_id):
        self.base_url = str(base_url or "").rstrip("/")
        self.client_id = str(client_id or "")
        self.sock = None
        self._connect()

    def _connect(self):
        parsed = urlparse(self.base_url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname
        if not host:
            raise RuntimeError("Invalid ComfyUI URL for websocket")
        port = parsed.port or (443 if scheme == "https" else 80)
        path = "/ws?clientId={}".format(self.client_id)

        raw = socket.create_connection((host, port), timeout=4.0)
        if scheme == "https":
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=host)
        raw.settimeout(0.25)
        self.sock = raw

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).format(path, host, port, key)
        self.sock.sendall(req.encode("utf-8"))

        response = self._recv_http_headers()
        if " 101 " not in response.split("\r\n", 1)[0]:
            raise RuntimeError("WebSocket upgrade failed: {}".format(response.split("\r\n", 1)[0]))

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def poll_progress(self, prompt_id, max_messages=8):
        """Read available frames and return latest progress payload for prompt_id."""
        if not self.sock:
            return None
        latest = None
        prompt_key = str(prompt_id)
        for _ in range(max_messages):
            frame = self._recv_frame_nonblocking()
            if frame is None:
                break
            opcode, payload = frame

            # Ping -> pong
            if opcode == 0x9:
                self._send_control_frame(0xA, payload)
                continue
            if opcode == 0x8:
                self.close()
                break
            if opcode != 0x1:
                continue
            try:
                msg = json.loads(payload.decode("utf-8"))
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue

            event_type = msg.get("type")
            event_data = msg.get("data", {})
            if event_type == "progress":
                if not isinstance(event_data, dict):
                    continue
                event_prompt = str(event_data.get("prompt_id", ""))
                if not event_prompt or event_prompt != prompt_key:
                    continue
                value = float(event_data.get("value", 0.0))
                maximum = float(event_data.get("max", 0.0))
                if maximum > 0:
                    latest = {
                        "percent": int(max(0, min(99, round((value / maximum) * 100.0)))),
                        "value": value,
                        "max": maximum,
                        "node": str(event_data.get("node", "")),
                        "type": "progress",
                    }
            elif event_type == "progress_state":
                # Newer Comfy events: data={prompt_id, nodes={node_id:{value,max}}}
                if not isinstance(event_data, dict):
                    continue
                event_prompt = str(event_data.get("prompt_id", ""))
                if not event_prompt or event_prompt != prompt_key:
                    continue
                nodes = event_data.get("nodes", {})
                if not isinstance(nodes, dict):
                    continue
                # Pick node state with the largest max to avoid setup-node 1/1 spikes.
                best = None
                for node_id, node_state in nodes.items():
                    if not isinstance(node_state, dict):
                        continue
                    value = float(node_state.get("value", 0.0))
                    maximum = float(node_state.get("max", 0.0))
                    if maximum > 0:
                        candidate = {
                            "percent": int(max(0, min(99, round((value / maximum) * 100.0)))),
                            "value": value,
                            "max": maximum,
                            "node": str(node_id),
                            "type": "progress_state",
                        }
                        if best is None or maximum > float(best.get("max", 0.0)):
                            best = candidate
                if best is not None:
                    latest = best
        return latest

    def _recv_http_headers(self):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 65536:
                break
        return data.decode("utf-8", errors="replace")

    def _recv_exact(self, size):
        chunks = []
        remaining = size
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket connection closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame_nonblocking(self):
        try:
            header = self.sock.recv(2)
            if not header:
                return None
        except socket.timeout:
            return None
        except OSError:
            return None

        if len(header) < 2:
            return None
        b1, b2 = header[0], header[1]
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F

        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]

        mask_key = b""
        if masked:
            mask_key = self._recv_exact(4)

        payload = self._recv_exact(length) if length > 0 else b""
        if masked and payload:
            payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(len(payload)))

        return opcode, payload

    def _send_control_frame(self, opcode, payload=b""):
        if self.sock is None:
            return
        payload = payload or b""
        first = 0x80 | (opcode & 0x0F)
        # Client frames must be masked.
        mask = os.urandom(4)
        length = len(payload)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length < (1 << 16):
            header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
        masked_payload = bytes(payload[i] ^ mask[i % 4] for i in range(length))
        self.sock.sendall(header + mask + masked_payload)


class ComfyClient:
    """Minimal ComfyUI client using stdlib HTTP."""

    def __init__(self, base_url):
        self.base_url = str(base_url or "").rstrip("/")

    @staticmethod
    def open_progress_socket(base_url, client_id):
        return ComfyProgressSocket(base_url, client_id)

    def ping(self, timeout=0.5):
        with urlopen("{}/system_stats".format(self.base_url), timeout=timeout) as response:
            return int(response.status) >= 200 and int(response.status) < 300

    def queue_prompt(self, prompt_graph, client_id):
        payload = json.dumps({"prompt": prompt_graph, "client_id": client_id}).encode("utf-8")
        req = Request(
            "{}/prompt".format(self.base_url),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=5.0) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as ex:
            details = ""
            try:
                error_data = json.loads(ex.read().decode("utf-8"))
                details = error_data.get("error", {}).get("type") or error_data.get("error", {}).get("message") or str(error_data)
            except Exception:
                details = str(ex)
            raise RuntimeError("ComfyUI prompt rejected: {}".format(details))
        return data.get("prompt_id")

    def list_checkpoints(self):
        """Return available checkpoint names from ComfyUI object info."""
        with urlopen("{}/object_info/CheckpointLoaderSimple".format(self.base_url), timeout=3.0) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Expected path:
        # CheckpointLoaderSimple -> input -> required -> ckpt_name -> [ [..names..], {...meta...} ]
        node_info = data.get("CheckpointLoaderSimple", {})
        required = node_info.get("input", {}).get("required", {})
        ckpt_input = required.get("ckpt_name", [])
        if not ckpt_input or not isinstance(ckpt_input, list):
            return []
        values = ckpt_input[0] if len(ckpt_input) > 0 else []
        if not isinstance(values, list):
            return []
        return [str(v) for v in values if str(v).strip()]

    def history(self, prompt_id):
        with urlopen("{}/history/{}".format(self.base_url, quote(str(prompt_id))), timeout=3.0) as response:
            return json.loads(response.read().decode("utf-8"))

    def progress(self):
        """Return ComfyUI /progress payload."""
        try:
            with urlopen("{}/progress".format(self.base_url), timeout=3.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as ex:
            if int(getattr(ex, "code", 0)) == 404:
                # Some ComfyUI versions don't expose /progress.
                return None
            raise

    def interrupt(self, prompt_id=None):
        payload = {}
        if prompt_id:
            payload["prompt_id"] = str(prompt_id)
        log.debug("ComfyClient interrupt request base_url=%s prompt_id=%s", self.base_url, payload.get("prompt_id", ""))
        req = Request(
            "{}/interrupt".format(self.base_url),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=3.0) as response:
            log.debug("ComfyClient interrupt response status=%s", int(response.status))
            return int(response.status) >= 200 and int(response.status) < 300

    def cancel_prompt(self, prompt_id):
        """Request ComfyUI to delete/cancel a prompt from the queue."""
        log.debug("ComfyClient cancel_prompt request base_url=%s prompt_id=%s", self.base_url, str(prompt_id))
        payload = json.dumps({"delete": [str(prompt_id)]}).encode("utf-8")
        req = Request(
            "{}/queue".format(self.base_url),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=3.0) as response:
            log.debug("ComfyClient cancel_prompt response status=%s", int(response.status))
            return int(response.status) >= 200 and int(response.status) < 300

    def queue(self):
        """Return ComfyUI queue state."""
        with urlopen("{}/queue".format(self.base_url), timeout=3.0) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def prompt_in_queue(prompt_id, queue_data):
        """Check if prompt_id appears in queue_running/queue_pending payload."""
        pid = str(prompt_id)
        if not isinstance(queue_data, dict):
            return False

        for key in ("queue_running", "queue_pending"):
            entries = queue_data.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                # Common format: [number, prompt_id, ...]
                if isinstance(entry, list) and len(entry) >= 2 and str(entry[1]) == pid:
                    return True
                # Defensive fallback for dict-like entries
                if isinstance(entry, dict):
                    if str(entry.get("prompt_id", "")) == pid:
                        return True
        return False

    @staticmethod
    def extract_image_outputs(history_entry, save_node_ids=None):
        """Return a flat list of image refs from a history entry."""
        outputs = []
        if not isinstance(history_entry, dict):
            return outputs
        node_outputs = history_entry.get("outputs", {})
        if not isinstance(node_outputs, dict):
            return outputs
        save_node_ids = set(str(node_id) for node_id in (save_node_ids or []))

        for node_id, node_out in node_outputs.items():
            if save_node_ids and str(node_id) not in save_node_ids:
                continue
            if not isinstance(node_out, dict):
                continue
            images = node_out.get("images", [])
            if not isinstance(images, list):
                continue
            for img in images:
                if not isinstance(img, dict):
                    continue
                if img.get("filename"):
                    outputs.append({
                        "filename": str(img.get("filename")),
                        "subfolder": str(img.get("subfolder", "")),
                        "type": str(img.get("type", "output")),
                    })
        return outputs

    def download_image(self, image_ref, destination_path):
        """Download a Comfy image reference to a local file path."""
        params = {
            "filename": image_ref.get("filename", ""),
            "subfolder": image_ref.get("subfolder", ""),
            "type": image_ref.get("type", "output"),
        }
        url = "{}/view?{}".format(self.base_url, urlencode(params))
        with urlopen(url, timeout=10.0) as response:
            data = response.read()

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        with open(destination_path, "wb") as handle:
            handle.write(data)
