# spark-with-s3a.Dockerfile
FROM bitnami/spark:3.5

USER root
RUN adduser --uid 1001 --disabled-password --gecos "" spark
USER 1001


# ARG HADOOP_VER=3.3.4
# ARG AWS_VER=1.12.620
# ARG DELTA_VER=3.1.0

# # ---- become root, install curl, download jars -------------------
# USER 0
# RUN install_packages curl && \       # <─ Bitnami helper to apt-get curl
#     mkdir -p /opt/extra-jars && \
#     curl -fsSL -o /opt/extra-jars/hadoop-aws.jar \
#       https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VER}/hadoop-aws-${HADOOP_VER}.jar && \
#     curl -fsSL -o /opt/extra-jars/aws-java-sdk-bundle.jar \
#       https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_VER}/aws-java-sdk-bundle-${AWS_VER}.jar && \
#     curl -fsSL -o /opt/extra-jars/delta-spark.jar \
#       https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/${DELTA_VER}/delta-spark_2.12-${DELTA_VER}.jar && \
#     curl -fsSL -o /opt/extra-jars/delta-storage.jar \
#       https://repo1.maven.org/maven2/io/delta/delta-storage/${DELTA_VER}/delta-storage-${DELTA_VER}.jar && \
#     chown -R 1001:root /opt/extra-jars

# # ---- drop back to Bitnami’s non-root user -----------------------
# USER 1001

# ENV SPARK_EXTRA_CLASSPATH=/opt/extra-jars/*
