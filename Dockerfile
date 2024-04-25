FROM public.ecr.aws/lambda/python:3.12

RUN dnf install -y wget xorg-x11-server-Xvfb gtk3-devel libnotify-devel nss libXScrnSaver alsa-lib

# Install Python libraries
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install

# Copy function code
COPY src/ /var/task/src/
RUN chmod +x /var/task/src/main.py

ENTRYPOINT ["/var/task/src/main.py"]
CMD ["python", "/var/task/src/main.py"]