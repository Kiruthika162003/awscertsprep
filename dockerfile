FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

HEALTHCHECK CMD streamlit health

EXPOSE 8501

CMD streamlit run app4.py --server.enableCORS false --server.enableXsrfProtection false