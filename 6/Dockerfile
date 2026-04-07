# Tutorial 6: Primary and replica nodes (Python stdlib only)
FROM python:3.12-slim

# So print() from primary/replica shows up in `docker compose logs` without delay
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY common.py primary.py replica.py ./

# Default: run primary (compose overrides for replica)
CMD ["python", "primary.py"]
