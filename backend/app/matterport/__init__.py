"""Matterport 3D property data platform.

Everything that talks to the Matterport GraphQL API lives here. The only network
path is MatterportClient, which routes every call through app/adapters/cache.py so
ingestion is deterministic and replayable offline.

See .kiro/specs/matterport-platform/ for requirements, design, and tasks.
"""
