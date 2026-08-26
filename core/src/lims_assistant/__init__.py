"""Lokaler LIMS-Probenassistent - Offline-Rechenkern.

Excel/VBA ist reine Oberflaeche; dieser Kern uebernimmt Import, Textextraktion,
OCR, Strukturierung, Normalisierung, Lernen, Confidence-Fusion und Export.
Kommunikation ausschliesslich ueber versionierte JSON-Jobdateien.
"""

from lims_assistant.version import APP_VERSION, SCHEMA_VERSION

__all__ = ["APP_VERSION", "SCHEMA_VERSION"]
