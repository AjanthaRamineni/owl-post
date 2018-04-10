FROM python:stretch
COPY requirements.txt owl-post/ /usr/src/app/ 
WORKDIR /usr/src/app
RUN [ ! -f config.yaml ] && { echo "Missing config file" 1>&2; exit 2; } || exit 0
RUN mkdir qdisambiguation_files
RUN pip install --no-cache-dir -r requirements.txt
CMD python hermes.py -r config.yaml


