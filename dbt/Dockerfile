FROM python:3.11-slim
RUN pip install --no-cache-dir dbt-postgres
WORKDIR /dbt
COPY . .
CMD ["sh", "-c", "dbt deps --profiles-dir . && dbt run --profiles-dir ."]
