FROM grafana/grafana:10.3.1

# Copy provisioning files (datasources, dashboards, etc.)
COPY provisioning /etc/grafana/provisioning

# Optionally copy dashboards if you have them in a subfolder
# COPY monitoring/grafana/dashboards /var/lib/grafana/dashboards

# Set permissions if needed
USER root
# RUN chown -R grafana:grafana /etc/grafana/provisioning
USER grafana
