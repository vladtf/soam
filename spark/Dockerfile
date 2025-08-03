# Dockerfile
FROM bitnami/spark:3.5

USER root
RUN groupadd --gid 1001 spark \
 && useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash --comment "Apache Spark" spark \
 && chown -R spark:spark /home/spark
USER spark

# Install network debugging tool
USER root
RUN install_packages curl net-tools iputils-ping

# Install Python 3 and pip
RUN install_packages python3 python3-pip iputils-ping curl \
 && ln -sf /usr/bin/python3 /usr/bin/python
