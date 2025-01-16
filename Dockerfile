FROM public.ecr.aws/lambda/python:3.12

# Add needed system dependencies
RUN dnf install -y wget xorg-x11-server-Xvfb gtk3-devel libnotify-devel nss libXScrnSaver alsa-lib tar

WORKDIR "${LAMBDA_TASK_ROOT}"

# Set environment variables for Python
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Copy function code
COPY src ${LAMBDA_TASK_ROOT}

# Install uv globally
RUN pip install uv

# Initialize uv and install dependencies
COPY pyproject.toml ${LAMBDA_TASK_ROOT}
RUN uv install

# Install Playwright browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium

# Default to Lambda handler, but allow override for CLI usage
ENTRYPOINT ["python"]
CMD ["-m", "main.lambda_handler"]