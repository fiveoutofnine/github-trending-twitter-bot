FROM python:3

COPY src/bot.py /src/
RUN pip install --upgrade pip
COPY requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt

CMD ["python3", "src/bot.py"]
