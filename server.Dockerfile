FROM synacktra/cillow:latest

# Uncomment the following line if you want cillow to use uv for package installation
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy your server script into the container
COPY server.py .

# Expose the port the server will listen on
EXPOSE 5556

# Define the command to start the server
CMD ["python", "server.py"]
