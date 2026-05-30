# Harness Extension Point

This directory is reserved for future external agent tools. Phase 1 keeps tool implementations in `backend/app/harness.py` so they are testable without external processes.

Future tools should expose:

- name
- description
- input schema
- deterministic output contract
- privacy notes for resume/JD handling

