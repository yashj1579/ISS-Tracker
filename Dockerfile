FROM python:3.12

COPY requirements.txt /code/requirements.txt
RUN pip install -r /code/requirements.txt

COPY iss_tracker.py /code/iss_tracker.py
COPY test_iss_tracker.py /code/test_iss_tracker.py

RUN chmod +rx /code/iss_tracker.py
RUN chmod +rx /code/test_iss_tracker.py

ENV PATH="/code:$PATH"

ENTRYPOINT ["python"]
CMD ["/code/iss_tracker.py"]
