FROM public.ecr.aws/lambda/python:3.12

# Add needed system dependencies
RUN dnf install -y wget xorg-x11-server-Xvfb gtk3-devel libnotify-devel nss libXScrnSaver alsa-lib tar

WORKDIR "${LAMBDA_TASK_ROOT}"

# Set environment variables for Python
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}:${PYTHONPATH}"

# Copy function code
COPY src ${LAMBDA_TASK_ROOT}

# Install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Install Playwright browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install

CMD ["main.scan_and_store_odds_portal_data"]