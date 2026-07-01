# Ελληνικό Local Rapid SCADA Telemetry Dashboard

Read-only backend dashboard project για ανάγνωση telemetry data από υπάρχον Rapid SCADA.

Το project δεν αντικαθιστά το Rapid SCADA. Λειτουργεί ως βοηθητικό backend layer που διαβάζει metadata από τα XML αρχεία του Rapid SCADA και current/live values από το Rapid SCADA Web API.

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

## PACKAGES

fastapi             → web API framework
uvicorn             → server που τρέχει το FastAPI
httpx               → HTTP client, πιθανότατα για κλήσεις προς Rapid SCADA API
pydantic            → validation / data models
pydantic-settings   → φόρτωση settings από .env
python-dotenv       → υποστήριξη .env
PyYAML              → YAML support, ίσως από παλιότερο config ή μελλοντική χρήση
watchfiles          → auto reload σε dev mode
websockets          → dependency/υποστήριξη server stack