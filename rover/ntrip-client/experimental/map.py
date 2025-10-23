"""
Provides human-readable mappings for u-blox NAV-PVT message fields.

This module contains dictionaries that translate integer codes from u-blox
GPS messages into descriptive strings. This is useful for logging and
debugging purposes.

The mappings are based on the u-blox protocol specification found below:
https://content.u-blox.com/sites/default/files/products/documents/u-blox7-V14_ReceiverDescriptionProtocolSpec_%28GPS.G7-SW-12001%29_Public.pdf
"""

fixType_map = {
    0: "No fix",
    1: "Dead reckoning only", 
    2: "2D fix",
    3: "3D fix",
    4: "GNSS + dead reckoning combined",
    5: "Time only fix"
}
"""dict: Maps the `fixType` field to a string description."""

gpsFixOk_map = {
    0: "Fix not available or invalid",
    1: "Fix valid"
}
"""dict: Maps the `gnssFixOk` flag to a string description."""

diffSoln_map = {
    0: "No differential corrections",
    1: "Differential corrections have been applied (RTK)"
}
"""dict: Maps the `diffSoln` flag to a string description."""