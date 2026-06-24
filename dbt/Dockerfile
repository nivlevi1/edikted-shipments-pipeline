FROM python:3.11-slim
RUN pip install --no-cache-dir dbt-postgres
WORKDIR /dbt
COPY . .
CMD ["dbt", "run", "--profiles-dir", "."]
