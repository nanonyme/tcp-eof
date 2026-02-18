# First stage: Build the Go program
FROM debian:bookworm-slim AS builder

# Install Go
RUN apt-get update && \
    apt-get install -y golang-go && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy source files
COPY go.mod ./
COPY main.go ./

# Build statically linked binary
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o tcp-eof main.go

# Second stage: Create minimal image with only the binary
FROM scratch

# Copy the binary from builder stage
COPY --from=builder /build/tcp-eof /tcp-eof

# Set the entrypoint to the program
ENTRYPOINT ["/tcp-eof"]

# Default port
CMD ["9999"]
