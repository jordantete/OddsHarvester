FROM public.ecr.aws/lambda/python:3.12

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Add needed system dependencies
RUN dnf install -y wget xorg-x11-server-Xvfb gtk3-devel libnotify-devel nss libXScrnSaver alsa-lib tar

# Set environment variables
ENV LAMBDA_TASK_ROOT=/var/task
WORKDIR "${LAMBDA_TASK_ROOT}"

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Copy function code
COPY src ${LAMBDA_TASK_ROOT}

# Ensure all referenced files are in the correct working directory
COPY pyproject.toml uv.lock README.md LICENSE.txt ${LAMBDA_TASK_ROOT}

# Initialize uv and install dependencies
RUN uv sync --frozen

# Install Playwright browser
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN pip install playwright

# Activate the virtual environment
ENV PATH="${LAMBDA_TASK_ROOT}/.venv/bin:$PATH"

# Set default command for local execution
CMD ["python3", "-m", "main"]