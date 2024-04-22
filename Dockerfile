# Stage 1: Download and unpack Chrome and ChromeDriver
FROM public.ecr.aws/lambda/python@sha256:bf65727dd64fa8cbe9ada6a6c29a3fa4f248c635599e770366f8ac21eef36630 as build

RUN dnf install -y unzip && \
    curl -Lo "/tmp/chromedriver-linux64.zip" "https://storage.googleapis.com/chrome-for-testing-public/123.0.6312.122/linux64/chromedriver-linux64.zip" && \
    curl -Lo "/tmp/chrome-linux64.zip" "https://storage.googleapis.com/chrome-for-testing-public/123.0.6312.122/linux64/chrome-linux64.zip" && \
    unzip /tmp/chromedriver-linux64.zip -d /opt/ && \
    unzip /tmp/chrome-linux64.zip -d /opt/

# Stage 2: Set up the Lambda runtime environment
FROM public.ecr.aws/lambda/python@sha256:bf65727dd64fa8cbe9ada6a6c29a3fa4f248c635599e770366f8ac21eef36630

# Install necessary libraries
RUN dnf install -y \
    atk cups-libs gtk3 libXcomposite alsa-lib \
    libXcursor libXdamage libXext libXi libXrandr libXScrnSaver \
    libXtst pango at-spi2-atk libXt xorg-x11-server-Xvfb \
    xorg-x11-xauth dbus-glib dbus-glib-devel nss mesa-libgbm

# Install Python libraries
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --from=build /opt/chrome-linux64 /opt/chrome
COPY --from=build /opt/chromedriver-linux64 /opt/

# Copy function code
COPY src/ /var/task/src/
RUN chmod +x /var/task/src/main.py

ENTRYPOINT ["/var/task/src/main.py"]
CMD ["src.main.scan_and_store_odds_portal_data"]
