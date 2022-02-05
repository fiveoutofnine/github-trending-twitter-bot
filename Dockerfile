FROM python:3.8-alpine

COPY src/bot.py /src/
COPY requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt

CMD ["python3", "src/bot.py"]
