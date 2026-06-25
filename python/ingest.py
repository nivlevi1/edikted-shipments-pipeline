import gzip
import io
import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

SRC_DIR      = Path(os.environ.get("SRC_DIR", "/app/src"))
POSTGRES_CONN = os.environ["POSTGRES_CONN"]


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
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def parse_csv(data: bytes, filename: str) -> pd.DataFrame:
    is_gz = filename.endswith(".gz") or filename.endswith(".zhtml")
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


def _table_name(filename: str) -> str:
    name = filename
    for ext in (".csv.gz", ".json.gz", ".csv", ".json", ".zhtml"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


def main():
    engine = create_engine(POSTGRES_CONN)

    files = sorted(SRC_DIR.iterdir())
    print(f"Found {len(files)} files in {SRC_DIR}")

    for path in files:
        filename = path.name
        data = path.read_bytes()

        if filename.endswith(".json.gz"):
            df = parse_json_gz(data, filename)
        elif filename.endswith(".csv.gz") or filename.endswith(".csv") or filename.endswith(".zhtml"):
            df = parse_csv(data, filename)
        else:
            print(f"Unknown type, skipping: {filename}")
            continue

        if df.empty:
            continue

        df["_source_file"] = filename
        table = _table_name(filename)
        df.to_sql(table, engine, schema="raw", if_exists="replace", index=False, chunksize=10_000)
        print(f"  {len(df):,} rows → raw.{table}")


if __name__ == "__main__":
    main()
