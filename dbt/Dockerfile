FROM python:3.11-slim
RUN pip install --no-cache-dir dbt-postgres
WORKDIR /dbt
COPY . .
ENV DBT_PROFILES_DIR=.
CMD ["sh", "-c", "dbt deps && dbt build"]
