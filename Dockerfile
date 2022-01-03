# Globals and input args
FROM python:3.9.9-alpine
RUN mkdir -p /app
WORKDIR /app

# Prepare our app requirements and install it...
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

# Install our code
COPY *.py /app/
RUN chmod a+x /app/main.py

# Setup our entrypoint command to run on docker run
CMD [ "python", "-u", "./main.py" ]
