# Globals and input args
FROM python:3.9.16-alpine3.17
WORKDIR /app

# Prepare our app requirements and install it...
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install our code
COPY *.py ./
RUN chmod a+x /app/main.py

# Setup our entrypoint command to run on docker run
CMD [ "python", "-u", "./main.py" ]
