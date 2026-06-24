# Ελληνικό Local Rapid SCADA Telemetry Dashboard

Read-only backend dashboard project για ανάγνωση telemetry data από υπάρχον Rapid SCADA.

Το project δεν αντικαθιστά το Rapid SCADA. Λειτουργεί ως βοηθητικό backend layer που διαβάζει metadata από τα XML αρχεία του Rapid SCADA και current/live values από το Rapid SCADA Web API.

## Κατάσταση project

Έχουν ολοκληρωθεί:

- Φάση 1: FastAPI backend skeleton, health endpoint, XML metadata loader.
- Φάση 2: Σύνδεση με Rapid SCADA Web API για current values και merge με metadata.

Δεν έχει υλοποιηθεί ακόμα frontend.

## Τεχνολογίες

- Python
- FastAPI
- Uvicorn
- httpx
- pydantic-settings
- python-dotenv

## Backend path

```text
backend/

## Βασικά endpoints

GET /api/health
GET /api/metadata/channels
GET /api/metadata/channels?active_only=true
GET /api/metadata/channels/{cnl_num}
GET /api/metadata/summary
GET /api/current/raw?cnl_nums=101,102,103
GET /api/current?cnl_nums=101,102,103
GET /api/current

## Metadata

backend/scada_project/BaseXML/

## Αρχεία που χρησιμοποιούνται μέχρι τώρα:

Cnl.xml
Device.xml
CommLine.xml
CnlStatus.xml

## Τα metadata καναλιών περιλαμβάνουν

cnl_num
active
name
tag_code
device_num
device_name
comm_line_num
comm_line_name
cnl_type_id
format_id
unit_id