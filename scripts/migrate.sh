#!/bin/bash
podman exec -it codeintel-api alembic upgrade head
