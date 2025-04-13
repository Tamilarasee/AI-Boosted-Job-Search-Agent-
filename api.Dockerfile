# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the base working directory
WORKDIR /code

# Copy requirements first to leverage Docker cache
COPY requirements.txt /code/

# Install dependencies specified in requirements.txt
# Explicitly upgrade pip and install uvicorn with standard extras
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "uvicorn[standard]"

# Copy the application code AFTER installing requirements
# This improves Docker layer caching if only code changes
COPY ./api/ /code/api/
COPY ./utils/ /code/utils/

# Set the final working directory for running the app
WORKDIR /code/api

# Tell Python to also look for modules in the /code directory
ENV PYTHONPATH="/code"

# Expose the port the app runs on
EXPOSE 8000
ENV PORT 8000 # Render will use this environment variable

# Shell form (DOES expand $PORT)
CMD uvicorn main:app --host 0.0.0.0 --port $PORT