# Rapid SCADA Telemetry Dashboard Backend

Local read-only FastAPI backend for Rapid SCADA telemetry metadata and analytics.

## Current phase

Phase 1 completed:
- Project skeleton
- Python virtual environment
- FastAPI backend
- Health endpoint
- XML metadata loader
- Metadata channels endpoint
- Metadata summary endpoint
- Single channel metadata endpoint

## Important security note

Real Rapid SCADA XML files are local-only and must not be committed.

Do not commit:

```text
backend/scada_project/BaseXML/Cnl.xml
backend/scada_project/BaseXML/Device.xml
backend/scada_project/BaseXML/CommLine.xml