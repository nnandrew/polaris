import socket

def get_local_ip(timeout: float = 1.0) -> str:
    """Return the machine's primary IPv4 address (e.g. 10.x.x.x).

    This uses a UDP socket to an external IP (no packets are sent) which
    forces the OS to choose the outgoing interface. If that fails it
    falls back to 127.0.0.1.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # doesn't actually send packets
            s.settimeout(timeout)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"