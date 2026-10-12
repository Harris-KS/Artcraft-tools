FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 ca-certificates dpkg libxkbcommon0 libwayland-client0 libx11-6 \
    libxrandr2 libxi6 libxcursor1 libxcb1 libegl1 libgl1 libvulkan1 \
    libfontconfig1 libfreetype6 libgtk-3-0t64 libasound2t64 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 artcraft \
    && mkdir /data /files && chown artcraft:artcraft /data /files
WORKDIR /opt/artcraft
COPY artcraft_edge.py mcp_bridge.py ./
USER artcraft
ENV ARTCRAFT_DATA=/data ARTCRAFT_FILES=/files
EXPOSE 8787
CMD ["python3", "artcraft_edge.py", "--serve", "--host", "0.0.0.0"]
