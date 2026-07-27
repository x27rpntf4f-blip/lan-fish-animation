import logging
import socket
import threading
import time

logger = logging.getLogger(__name__)


class HostInfo:
    def __init__(self, hostname, ip, port, reachable_ip=None):
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.reachable_ip = reachable_ip if reachable_ip else ip
        self.host_id = 0
        self.position = 0
        self.last_heartbeat = time.time()

    @staticmethod
    def make_key(ip, port):
        return f"{ip}:{port}"

    def key(self):
        return HostInfo.make_key(self.ip, self.port)

    def __repr__(self):
        return f"Host(id={self.host_id}: {self.ip}:{self.port})"


class HostRegistry:
    def __init__(self, port):
        self.hosts = {}  # "ip:port" → HostInfo
        self.my_hostname = socket.gethostname()
        self.my_ip = self._get_my_ip()
        self.my_port = port
        self.my_key = HostInfo.make_key(self.my_ip, port)
        self.my_id = 0
        self.left = None  # key of left neighbor
        self.right = None  # key of right neighbor

    @staticmethod
    def _get_my_ip():
        # Strategy 1: connect to public DNS → picks the default-route interface
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 53))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception as exc:
            logger.debug(
                "Default-route IP probe failed",
                extra={"event": "local_ip_probe_failed", "error": str(exc)},
            )

        # Strategy 2: old method (may pick wrong interface on multi-homed machines
        # with virtual adapters, but works as a fallback)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception as exc:
            logger.debug(
                "Fallback IP probe failed",
                extra={"event": "local_ip_fallback_failed", "error": str(exc)},
            )
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def add_or_update(self, hostname, ip, port, reachable_ip=None):
        key = HostInfo.make_key(ip, port)
        if key == self.my_key:
            return
        if key not in self.hosts:
            self.hosts[key] = HostInfo(hostname, ip, port, reachable_ip)
        else:
            h = self.hosts[key]
            h.hostname = hostname
            h.port = port
            h.last_heartbeat = time.time()
            if reachable_ip:
                h.reachable_ip = reachable_ip

        # Also keep track of known port->key mappings so that
        # heartbeats arriving from different local IPs (multi-homed
        # machines) can still be matched to the right host.
        if not hasattr(self, "_port_keys"):
            self._port_keys = {}
        port_key = f"{port}"
        if port_key not in self._port_keys:
            self._port_keys[port_key] = []
        if key not in self._port_keys[port_key]:
            self._port_keys[port_key].append(key)

    def heartbeat(self, ip, port, reachable_ip=None):
        # 1) Exact match by (ip, port) — works for single-interface hosts
        key = HostInfo.make_key(ip, port)
        if key in self.hosts:
            self.hosts[key].last_heartbeat = time.time()
            if reachable_ip and reachable_ip != self.hosts[key].reachable_ip:
                self.hosts[key].reachable_ip = reachable_ip
            return

        # 2) Match by (reachable_ip, port) — catches multi-homed machines
        #    whose self-reported IP differs from the actual source address.
        if reachable_ip:
            alt_key = HostInfo.make_key(reachable_ip, port)
            if alt_key in self.hosts:
                self.hosts[alt_key].last_heartbeat = time.time()
                # reachable_ip already matches the key, no update needed
                return

        # 3) Port-based fallback — only update hosts whose reachable_ip
        #    matches the sender.  Without this guard a host would keep
        #    every other host on the same port "alive" by receiving its
        #    own looped-back broadcasts — dead peers would never time out.
        port_key = f"{port}"
        mapped_list = getattr(self, "_port_keys", {}).get(port_key, [])
        for mapped in mapped_list:
            if mapped not in self.hosts:
                continue
            h = self.hosts[mapped]
            # Only refresh if the sender's IP matches this host's
            # reachable_ip.  This prevents cross-contamination when
            # multiple hosts share the same port (the default).
            if reachable_ip and h.reachable_ip and h.reachable_ip != reachable_ip:
                continue
            h.last_heartbeat = time.time()
            if reachable_ip and reachable_ip != h.reachable_ip:
                h.reachable_ip = reachable_ip

    def remove_by_key(self, key):
        self.hosts.pop(key, None)
        # Clean up port→key mappings so stale entries don't accumulate
        if hasattr(self, "_port_keys"):
            for port_key, keys in list(self._port_keys.items()):
                if key in keys:
                    keys.remove(key)
                if not keys:
                    del self._port_keys[port_key]

    def check_timeout(self, timeout=10):
        now = time.time()
        gone = [key for key, h in self.hosts.items() if now - h.last_heartbeat > timeout]
        return gone

    def rebuild_topology(self):
        all_keys = sorted([self.my_key] + list(self.hosts.keys()))
        for i, key in enumerate(all_keys):
            if key == self.my_key:
                self.my_id = i
            elif key in self.hosts:
                self.hosts[key].host_id = i
                self.hosts[key].position = i

        my_idx = all_keys.index(self.my_key)
        n = len(all_keys)
        # Linear strip topology: no wrap-around
        # left = previous host in sorted order (or None if at leftmost end)
        # right = next host in sorted order (or None if at rightmost end)
        self.left = all_keys[my_idx - 1] if my_idx > 0 else None
        self.right = all_keys[my_idx + 1] if my_idx < n - 1 else None

    def get_host_by_id(self, host_id):
        for h in self.hosts.values():
            if h.host_id == host_id:
                return h
        return None

    def get_host_by_key(self, key):
        return self.hosts.get(key)

    def host_count(self):
        return len(self.hosts) + 1

    def my_topology_entry(self):
        return {
            "host_id": self.my_id,
            "position": self.my_id,
            "ip": self.my_ip,
            "port": self.my_port,
        }


class NetworkManager:
    def __init__(self, start_port=6000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError as exc:
                logger.debug(
                    "SO_REUSEPORT is unavailable",
                    extra={"event": "socket_option_unavailable", "error": str(exc)},
                )
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.port = self._bind(start_port)
        # Always broadcast to the well-known port range, not
        # the instance's own port, so cross-port instances receive
        self.broadcast_base = 6000
        self.running = False
        self.thread = None
        self._hb_data = None  # heartbeat payload set by main thread
        self._hb_registry = None  # registry snapshot for heartbeat

    def _bind(self, port):
        for off in range(10):
            try:
                self.sock.bind(("0.0.0.0", port + off))
                return port + off
            except OSError as exc:
                logger.debug(
                    "UDP port is unavailable",
                    extra={
                        "event": "socket_bind_failed",
                        "peer": f"0.0.0.0:{port + off}",
                        "error": str(exc),
                    },
                )
                continue
        raise RuntimeError(f"Cannot bind to any port {port}-{port + 9}")

    def start_listen(self, queue):
        self.running = True
        self.thread = threading.Thread(target=self._loop, args=(queue,), daemon=True)
        self.thread.start()

    def send_heartbeat_async(self, data, registry):
        """Store heartbeat data so the network thread sends it.
        Returns immediately — no sendto() on the main thread."""
        self._hb_data = data
        self._hb_registry = registry

    def _loop(self, queue):
        self.sock.settimeout(0.5)
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                queue.put((data, addr))
            except TimeoutError:
                pass
            except Exception as exc:
                logger.warning(
                    "UDP listener failed",
                    extra={"event": "packet_receive_failed", "error": str(exc)},
                )

            # Send any pending heartbeat from the network thread so
            # sendto() latency never blocks the main render loop.
            # We ONLY unicast to known peers — no broadcast, because
            # broadcast self-loopback creates GIL contention between
            # the network thread (sendto) and the main render thread.
            # Discovery of new hosts is handled by HELLO at startup
            # and heartbeat-triggered discovery in the msg handler.
            if self._hb_data is not None:
                data = self._hb_data
                reg = self._hb_registry
                self._hb_data = None
                self._hb_registry = None
                if reg is not None:
                    self.send_known(data, reg)  # heartbeat: unicast
                else:
                    self.broadcast(data)  # discovery: broadcast

    def broadcast(self, data):
        """Send a single broadcast to the well-known port.  One hop is
        enough — across machines every host binds to the same default
        port, and within a single machine we reach peers via unicast."""
        try:
            self.sock.sendto(data, ("255.255.255.255", self.broadcast_base))
        except OSError as exc:
            logger.warning(
                "UDP broadcast failed",
                extra={
                    "event": "packet_broadcast_failed",
                    "peer": f"255.255.255.255:{self.broadcast_base}",
                    "error": str(exc),
                },
            )

    def send(self, ip, port, data):
        try:
            self.sock.sendto(data, (ip, port))
        except OSError as exc:
            logger.warning(
                "UDP send failed",
                extra={
                    "event": "packet_send_failed",
                    "peer": f"{ip}:{port}",
                    "error": str(exc),
                },
            )

    def send_known(self, data, registry):
        """Unicast *data* to every host currently in the registry.
        Used for heartbeats so known peers get reliable delivery
        without needing the 10-port broadcast hammer."""
        for h in registry.hosts.values():
            self.send(h.reachable_ip, h.port, data)

    def shutdown(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        try:
            self.sock.close()
        except Exception as exc:
            logger.debug(
                "UDP socket close failed",
                extra={"event": "socket_close_failed", "error": str(exc)},
            )
