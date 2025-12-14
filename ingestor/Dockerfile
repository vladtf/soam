# ---------- base image ----------
FROM python:3.12-slim

# ---------- system packages ----------
# • openjdk: Try JDK 17 first (Bookworm), fallback to JDK 21 (Trixie)
# • procps: supplies the `ps` command Spark's bootstrap script calls
RUN apt-get update && \
    (apt-get install -y --no-install-recommends openjdk-17-jre-headless || \
     apt-get install -y --no-install-recommends openjdk-21-jre-headless) && \
    apt-get install -y --no-install-recommends \
        procps \
        iputils-ping \
        curl \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ---------- Java env ----------
# Create symlink to installed Java version for consistent JAVA_HOME
RUN if [ -d /usr/lib/jvm/java-21-openjdk-amd64 ]; then \
      ln -sf /usr/lib/jvm/java-21-openjdk-amd64 /usr/lib/jvm/java-openjdk; \
    else \
      ln -sf /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/java-openjdk; \
    fi
ENV JAVA_HOME=/usr/lib/jvm/java-openjdk
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
    