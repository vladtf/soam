# ---------- base image ----------
FROM python:3.12-slim

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

# ---------- Java env ----------
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# ---------- Python deps ----------
RUN pip install --no-cache-dir pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./
# ignore-pipfile avoids hash-mismatch failures during CI/CD
RUN pipenv install --deploy --system --ignore-pipfile

# ---------- project code ----------
COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
    