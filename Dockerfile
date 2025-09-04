# Stage 1: Base setup with dependencies
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble AS base

# Install uv globally
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR "${LAMBDA_TASK_ROOT}"

# Copy application files
COPY src ${LAMBDA_TASK_ROOT}/src
COPY pyproject.toml uv.lock README.md LICENSE.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN uv sync --frozen

# Stage 2: AWS Lambda runtime
FROM public.ecr.aws/lambda/python:3.12 AS aws-lambda

# Copy all files from the base stage
COPY --from=base /var/task /var/task

# Set Lambda runtime handler
CMD ["lambda_handler"]

# Stage 3: Local development/testing
FROM base AS local-dev

# Activate the virtual environment
ENV PATH="${LAMBDA_TASK_ROOT}/.venv/bin:$PATH"

# Set default command for local testing
CMD ["xvfb-run", "--", "python3", "-m", "src.main"]

