import os
from pathlib import Path

import boto3

BUCKET  = os.environ["AWS_S3_BUCKET"]
PREFIX  = os.environ["AWS_S3_PREFIX"]
SRC_DIR = Path(os.environ.get("SRC_DIR", "/app/src"))


def main():
    s3 = boto3.client("s3")
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX)
        for obj in page.get("Contents", [])
    ]
    print(f"Found {len(keys)} objects in s3://{BUCKET}/{PREFIX}")

    for key in keys:
        filename = key.split("/")[-1]
        if not filename:
            continue
        dest = SRC_DIR / filename
        print(f"  {key} → {dest}")
        s3.download_file(BUCKET, key, str(dest))

    print(f"Done. {len(keys)} files in {SRC_DIR}")


if __name__ == "__main__":
    main()
