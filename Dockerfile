# Base image
FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install BPF tools and dependencies for bpftrace
# - bpftrace: The high-level tracing language you want to use
# - bpfcc-tools: Collection of BPF-based tools (often complements bpftrace)
# - linux-bpf-tools: Kernel's bpftool utility (useful for BPF introspection)
# - clang & llvm: Compiler infrastructure for BPF programs
# - libbpf-dev: Library for BPF applications
# - linux-headers-generic: Kernel headers for compiling BPF programs.
#                          Crucial for bpftrace to work, as BPF programs
#                          are often compiled against the running kernel's headers.
#                          Note: These headers are for a generic kernel. For optimal
#                          compatibility, the host's exact kernel headers should be
#                          available, which usually means mounting /lib/modules and /usr/src
#                          from the host.
# - git, make, gcc: General development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    bpftrace \
    bpfcc-tools \
    clang \
    llvm \
    libbpf-dev \
    linux-headers-generic \
    git \
    make \
    gcc \
    postgresql \
    postgresql-client \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Overwrite pg_hba.conf for full trust authentication for local connections
RUN echo "local   all             all                                     trust" > /etc/postgresql/14/main/pg_hba.conf && \
    echo "host    all             all             127.0.0.1/32            trust" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "host    all             all             ::1/128                 trust" >> /etc/postgresql/14/main/pg_hba.conf

# Set a working directory
WORKDIR /app

# Copy application files before installing dependencies
COPY ./server /app/server
COPY ./static /app/static

# Install uv, create venv in a non-mounted location, and install dependencies
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:$PATH" && \
    uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python fastapi uvicorn websockets psycopg2-binary

# Expose the port the app runs on
EXPOSE 8000

# Default command to start services and the app
# The working directory is changed to /app/server so uvicorn can find main:app
CMD ["bash", "-c", "service postgresql start && echo 'PostgreSQL started.' && cd /app/server && /opt/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000"]
