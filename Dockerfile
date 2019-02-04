FROM python:3.7-slim

COPY requirements.txt .

RUN pip install --upgrade pip setuptools \
 && pip install -r requirements.txt \
 && rm requirements.txt

COPY . /tmp/dustdevil/

RUN cd /tmp/dustdevil \
 && python setup.py install \
 && cd / \
 && rm -rf /tmp/dustdevil

COPY tests/ /tests/

WORKDIR /tests

CMD pytest