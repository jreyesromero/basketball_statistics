# Bake config into the image so runtime bind mounts are not required for /etc/promtail
# (avoids empty-directory bind issues on some Colima / Docker setups).
FROM grafana/promtail:2.9.8
COPY promtail/config.yml /etc/promtail/config.yml
