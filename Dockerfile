FROM python:3.10

RUN mkdir /<work_dir>

WORKDIR /<work_dir>

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN chmod +x /<work_dir>/docker/*.sh

ENTRYPOINT /<work_dir>/docker/init.sh
