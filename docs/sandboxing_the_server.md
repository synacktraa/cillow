This guide will show you how to securely host the Cillow server using Docker, leveraging the Cillow base image for isolated and consistent deployments.

---

### 1. **Prerequisites**
- Docker installed on your system
- A [`server.py`](https://github.com/synacktraa/cillow/blob/main/server.py) file to configure and run the Cillow server. This file sets up and starts the server, optionally with custom patches or configurations (see [Using Cillow guide](./quickstart/using_cillow.md)).

---

### 2. **Creating the Dockerfile**
Create a `Dockerfile` in the same directory as your `server.py` file:

```dockerfile
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
```

---

### 3. **Building the Docker Image**
Run the following command to build the Docker image. The `-t` flag tags the image as `cillow-server`:

```bash
docker build -t cillow-server .
```

---

### 4. **Running the Docker Container**
Launch the container using the built image. The `--init` flag ensures proper process handling, and `-it` keeps the container interactive:

```bash
docker run --init -it -p 5556:5556 --name cillow-server cillow-server
```

This maps port `5556` from the container to your local machine, enabling client connections.

---

### 5. **Accessing the Sandboxed Server**
Once the container is running, the Cillow server will be available at `localhost:5556`. Use `cillow.Client` to interact with the server as explained in the [Using Cillow guide](./quickstart/using_cillow.md#interacting-with-the-server).

---

### 6. **Customizing Your Server**
Enhance your server with additional features by:
- Adding custom patches
- Configuring interpreter limits or other server parameters

Simply modify your `server.py`, rebuild the Docker image, and restart the container with updated settings.
