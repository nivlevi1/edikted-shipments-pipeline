import gzip
import io
import json
import os

import boto3
import pandas as pd
from sqlalchemy import create_engine

BUCKET = os.environ["AWS_S3_BUCKET"]
PREFIX = os.environ["AWS_S3_PREFIX"]
POSTGRES_CONN = os.environ["POSTGRES_CONN"]

_JSON_RENAMES = {
    "inserdatetime": "insert_datetime",
    "_warehouse_invoice": "warehouse_invoice",
    "_warehouse_fees": "warehouse_fees",
    "address": "main_address",
}


def _fix_malformed_json(raw_bytes: bytes) -> bytes:
    fixed = raw_bytes.replace(b"\x27\x27\x27\x27", b"")
    fixed = fixed.replace(b"\x5c\x6e", b" ")
    return fixed


def _is_html(data: bytes) -> bool:
    try:
        return data[:200].decode("utf-8", errors="replace").strip().startswith("<")
    except Exception:
        return False


def parse_json_gz(data: bytes, filename: str) -> pd.DataFrame:
    raw = gzip.decompress(data)
    try:
        records = json.loads(raw)
    except json.JSONDecodeError:
        print(f"{filename}: malformed JSON — attempting repair")
        records = json.loads(_fix_malformed_json(raw))
    df = pd.DataFrame(records, dtype=str)
    df.rename(columns=_JSON_RENAMES, inplace=True)
    return df


def parse_csv(data: bytes, filename: str) -> pd.DataFrame:
    is_gz = filename.endswith(".gz")
    raw = gzip.decompress(data) if is_gz else data
    if _is_html(raw):
        print(f"{filename}: detected as HTML, skipping")
        return pd.DataFrame()
    return pd.read_csv(
        io.BytesIO(data),
        compression="gzip" if is_gz else None,
        dtype=str,
        keep_default_na=False,
    )


def main():
    s3 = boto3.client("s3")
    engine = create_engine(POSTGRES_CONN)

    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX)
        for obj in page.get("Contents", [])
    ]
    print(f"Found {len(keys)} objects in s3://{BUCKET}/{PREFIX}")

    frames = []
    for key in keys:
        filename = key.split("/")[-1]
        if not filename:
            continue
        print(f"Downloading {key}")
        data = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()

        if filename.endswith(".json.gz"):
            df = parse_json_gz(data, filename)
        elif filename.endswith(".csv.gz") or filename.endswith(".csv"):
            df = parse_csv(data, filename)
        else:
            print(f"Unknown type, skipping: {filename}")
            continue

        if df.empty:
            continue

        df["_source_file"] = filename
        frames.append(df)
        print(f"  {len(df):,} rows from {filename}")

    if not frames:
        print("No data loaded from S3")
        return

    combined = pd.concat(frames, ignore_index=True)
    print(f"Total: {len(combined):,} rows, {len(combined.columns)} columns")

    combined.to_sql(
        "shipments",
        engine,
        schema="raw",
        if_exists="replace",
        index=False,
        chunksize=10_000,
    )
    print("Loaded into raw.shipments ✓")


if __name__ == "__main__":
    main()
