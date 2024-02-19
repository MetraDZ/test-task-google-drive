
FROM python:3.11
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt 
COPY ./main.py /code/main.py
COPY ./functions.py /code/functions.py
COPY ./settings.yaml /code/settings.yaml
COPY ./index.html /code/index.html
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]