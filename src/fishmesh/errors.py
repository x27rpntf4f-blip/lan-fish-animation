class FishMeshError(Exception):
    """Base class for recoverable FishMesh errors."""


class PacketDecodeError(FishMeshError, ValueError):
    """A datagram is malformed or unsupported and must be discarded."""
