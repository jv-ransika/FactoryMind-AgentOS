from __future__ import annotations

import os
from typing import Any


def required_env_contract() -> list[str]:
    return [
        "AGENT_OS_ENV",
        "AGENT_OS_POSTGRES_DSN",
        "AGENT_OS_REDIS_URL",
        "AGENT_OS_JWT_ISSUER",
        "AGENT_OS_JWT_AUDIENCE",
        "OPENAI_API_KEY",
        "OTEL_SERVICE_NAME",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    ]


def render_ecs_task(role: str, image: str = "factorymind-agentos:latest") -> dict[str, Any]:
    if role not in {"service", "worker"}:
        raise ValueError("role must be service or worker")
    cmd = ["agent-os", "serve", "--host", "0.0.0.0", "--port", "8000"] if role == "service" else ["agent-os", "worker", "run"]
    return {
        "family": f"agent-os-{role}",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "512",
        "memory": "1024",
        "executionRoleArn": os.getenv("AGENT_OS_ECS_EXEC_ROLE_ARN", "arn:aws:iam::123456789012:role/ecsTaskExecutionRole"),
        "taskRoleArn": os.getenv("AGENT_OS_ECS_TASK_ROLE_ARN", "arn:aws:iam::123456789012:role/agentOsTaskRole"),
        "containerDefinitions": [
            {
                "name": f"agent-os-{role}",
                "image": image,
                "essential": True,
                "command": cmd,
                "portMappings": [] if role == "worker" else [{"containerPort": 8000, "protocol": "tcp"}],
                "environment": [{"name": key, "value": f"${{{key}}}"} for key in required_env_contract()],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/factorymind-agentos",
                        "awslogs-region": os.getenv("AWS_REGION", "us-east-1"),
                        "awslogs-stream-prefix": role,
                    },
                },
                "healthCheck": {
                    "command": ["CMD-SHELL", "curl -f http://localhost:8000/healthz || exit 1"] if role == "service" else ["CMD-SHELL", "echo ok"],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 20,
                },
            }
        ],
    }

