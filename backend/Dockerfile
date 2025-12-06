# ---------- base image ----------
FROM python:3.12-slim

# ---------- Version definitions ----------
ENV DELTA_VERSION=3.1.0 \
    HADOOP_VERSION=3.3.4 \
    AWS_SDK_VERSION=1.12.620 \
    ANTLR_VERSION=4.9.3 \
    SCALA_VERSION=2.12

# ---------- system packages ----------
# • openjdk-21-jre-headless  → JRE for Spark 3.5 (JDK 17 no longer available in Debian trixie)
# • procps                  → supplies the `ps` command Spark's bootstrap script calls
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-21-jre-headless \
        procps \
        iputils-ping \
        curl \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ---------- Spark dependencies ----------
# Pre-download Spark dependencies to avoid runtime Ivy downloads
# Using Delta Lake ${DELTA_VERSION} which is compatible with Spark 3.5
ENV SPARK_LIBS=/opt/spark-libs

RUN mkdir -p $SPARK_LIBS && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    # Delta Lake jars
    curl -L --retry 3 -o $SPARK_LIBS/delta-spark_${SCALA_VERSION}-${DELTA_VERSION}.jar \
        https://repo1.maven.org/maven2/io/delta/delta-spark_${SCALA_VERSION}/${DELTA_VERSION}/delta-spark_${SCALA_VERSION}-${DELTA_VERSION}.jar && \
    curl -L --retry 3 -o $SPARK_LIBS/delta-storage-${DELTA_VERSION}.jar \
        https://repo1.maven.org/maven2/io/delta/delta-storage/${DELTA_VERSION}/delta-storage-${DELTA_VERSION}.jar && \
    # AWS and Hadoop dependencies
    curl -L --retry 3 -o $SPARK_LIBS/hadoop-aws-${HADOOP_VERSION}.jar \
        https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar && \
    curl -L --retry 3 -o $SPARK_LIBS/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar \
        https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar && \
    # Additional dependencies
    curl -L --retry 3 -o $SPARK_LIBS/antlr4-runtime-${ANTLR_VERSION}.jar \
        https://repo1.maven.org/maven2/org/antlr/antlr4-runtime/${ANTLR_VERSION}/antlr4-runtime-${ANTLR_VERSION}.jar && \
    # Cleanup
    apt-get purge -y curl && \
    rm -rf /var/lib/apt/lists/*

# ---------- Java environment ----------
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# ---------- Python environment ----------
RUN pip install --no-cache-dir pipenv

WORKDIR /app

# Install Python dependencies
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system --ignore-pipfile

# ---------- Application code ----------
COPY . .

# ---------- Spark configuration ----------
ENV SPARK_JARS="$SPARK_LIBS/delta-spark_${SCALA_VERSION}-${DELTA_VERSION}.jar,$SPARK_LIBS/delta-storage-${DELTA_VERSION}.jar,$SPARK_LIBS/hadoop-aws-${HADOOP_VERSION}.jar,$SPARK_LIBS/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar,$SPARK_LIBS/antlr4-runtime-${ANTLR_VERSION}.jar"
ENV PYSPARK_SUBMIT_ARGS="--jars $SPARK_JARS pyspark-shell"

# ---------- Container configuration ----------
EXPOSE 8000 41397 41398
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
    