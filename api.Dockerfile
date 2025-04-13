    # Use an official Python runtime as a parent image
    FROM python:3.11-slim

    # Set environment variables
    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1

    # Set the working directory in the container
    WORKDIR /code

    # Install system dependencies if needed (e.g., for specific libraries)
    # RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

    # Copy the requirements file into the container at /code
    # We copy requirements first to leverage Docker cache
    COPY requirements.txt /code/

    # Install any needed packages specified in requirements.txt
    # We use --no-cache-dir to reduce image size
    RUN pip install --no-cache-dir --upgrade pip
    RUN pip install --no-cache-dir -r /code/requirements.txt

    # Copy the necessary application code into the container
    COPY ./api/ /code/api/
    COPY ./utils/ /code/utils/

    # Change working directory into the api folder where main.py is
    WORKDIR /code/api

    # Make port 8000 available to the world outside this container
    # Render will map its internal port to this one, often overriding with $PORT
    EXPOSE 8000

    # Define environment variable for the port (Render uses this)
    ENV PORT 8000

    # Run uvicorn when the container launches
    # Use 0.0.0.0 to allow connections from outside the container
    # The port is dynamically set by Render via the $PORT env var
    CMD ["python", "main.py"]