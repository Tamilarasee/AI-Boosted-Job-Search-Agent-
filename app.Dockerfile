    # Use an official Python runtime as a parent image
    FROM python:3.11-slim

    # Set environment variables
    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1

    # Set the working directory in the container
    WORKDIR /code/app

    # Copy the requirements file into the container at /code
    COPY requirements.txt /code/

    # Install any needed packages specified in requirements.txt
    RUN pip install --no-cache-dir --upgrade pip
    RUN pip install --no-cache-dir -r /code/requirements.txt

    # Copy the frontend application code into the container at /code/app
    COPY ./app/ /code/app/

    # Make port 8501 available (Streamlit's default)
    EXPOSE 8501

    # Healthcheck (Optional but good practice for platforms like Render)
    # Checks if Streamlit is running and healthy
    HEALTHCHECK CMD streamlit hello --server.headless true

    # Run streamlit when the container launches
    # Use 0.0.0.0 to allow connections from outside
    # Port 8501 is the default Streamlit port
    CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
