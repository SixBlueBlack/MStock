FROM python:3.10

RUN mkdir /MStock

WORKDIR /MStock

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN chmod +x /MStock/docker/*.sh

ENTRYPOINT /MStock/docker/init.sh
