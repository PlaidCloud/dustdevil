FROM python:3.9-slim
RUN apt-get update && apt-get install -y git gcc libhdf5-dev locales && echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools \
 && pip install -r requirements.txt \
 && pip install pylint \
 && rm requirements.txt

ADD . /tmp/dustdevil/
WORKDIR /tmp/dustdevil/
ENV PYTHONPATH="$PYTHONPATH:/tmp/dustdevil"
CMD ((git diff --name-only origin/master..$GIT_COMMIT) | grep .py$) | xargs -r -n1 pylint -j 0 -f parseable -r no>pylint.log
