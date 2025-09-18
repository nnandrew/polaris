import socket

def get_local_ip(timeout: float = 1.0) -> str:
    """Gets the primary local IP address of the machine.

    This function determines the local IP address by creating a UDP socket and
    connecting to an external address (Google's DNS). This forces the OS to
    select the appropriate network interface. No actual data is sent.

    Args:
        timeout (float): The socket timeout in seconds. Defaults to 1.0.

    Returns:
        str: The local IPv4 address as a string, or "127.0.0.1" if the
             lookup fails.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # doesn't actually send packets
            s.settimeout(timeout)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"