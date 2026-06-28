import socket
import threading
import time

from message import (
    HEADER_SIZE, MSG_HELLO, MSG_ACK, MSG_HEARTBEAT, MSG_TOPOLOGY,
    MSG_TRANSFER, MSG_GOODBYE, MSG_NAMES,
    pack_hello, pack_ack, pack_heartbeat, pack_topology, pack_goodbye,
    unpack_header, unpack_hello, unpack_ack, unpack_topology
)


class HostInfo:
    def __init__(self, hostname, ip, port):
        self.hostname = hostname
        self.ip = ip
        self.port = port
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
        self.hosts = {}          # "ip:port" → HostInfo
        self.my_hostname = socket.gethostname()
        self.my_ip = self._get_my_ip()
        self.my_port = port
        self.my_key = HostInfo.make_key(self.my_ip, port)
        self.my_id = 0
        self.left = None         # key of left neighbor
        self.right = None        # key of right neighbor

    @staticmethod
    def _get_my_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def add_or_update(self, hostname, ip, port):
        key = HostInfo.make_key(ip, port)
        if key == self.my_key:
            return
        if key not in self.hosts:
            self.hosts[key] = HostInfo(hostname, ip, port)
        else:
            h = self.hosts[key]
            h.hostname = hostname
            h.port = port
            h.last_heartbeat = time.time()

    def heartbeat(self, ip, port):
        key = HostInfo.make_key(ip, port)
        if key in self.hosts:
            self.hosts[key].last_heartbeat = time.time()

    def remove_by_key(self, key):
        self.hosts.pop(key, None)

    def check_timeout(self, timeout=10):
        now = time.time()
        gone = [key for key, h in self.hosts.items()
                if now - h.last_heartbeat > timeout]
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
        self.left = all_keys[my_idx - 1] if my_idx > 0 else None
        self.right = all_keys[my_idx + 1] if my_idx < len(all_keys) - 1 else None

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
        return {"host_id": self.my_id, "position": self.my_id}


class NetworkManager:
    def __init__(self, start_port=6000):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.port = self._bind(start_port)
        # Always broadcast to the well-known port range, not
        # the instance's own port, so cross-port instances receive
        self.broadcast_base = 6000
        self.running = False
        self.thread = None

    def _bind(self, port):
        for off in range(10):
            try:
                self.sock.bind(("0.0.0.0", port + off))
                return port + off
            except OSError:
                continue
        raise RuntimeError(f"Cannot bind to any port {port}-{port + 9}")

    def start_listen(self, queue):
        self.running = True
        self.thread = threading.Thread(target=self._loop, args=(queue,), daemon=True)
        self.thread.start()

    def _loop(self, queue):
        self.sock.settimeout(0.5)
        while self.running:
            try:
                data, addr = self.sock.recvfrom(512)
                queue.put((data, addr))
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[NET-ERR] listener: {e}")

    def broadcast(self, data):
        for p in range(self.broadcast_base, self.broadcast_base + 10):
            try:
                self.sock.sendto(data, ("255.255.255.255", p))
            except OSError:
                pass

    def send(self, ip, port, data):
        try:
            self.sock.sendto(data, (ip, port))
        except OSError:
            pass

    def shutdown(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        try:
            self.sock.close()
        except Exception:
            pass
