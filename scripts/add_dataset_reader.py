"""D2 helper: add a READER entry for one principal to a dataset JSON exported by `bq show`.

Usage: python3 scripts/add_dataset_reader.py ds.json SERVICE_ACCOUNT_EMAIL
It edits ds.json in place (idempotent); `bq update --source ds.json` applies it.
"""
import json
import sys

path, member = sys.argv[1], sys.argv[2]
ds = json.load(open(path))
access = ds.setdefault("access", [])
entry = {"role": "READER", "userByEmail": member}
if entry not in access:
    access.append(entry)
json.dump(ds, open(path, "w"), indent=1)
print(f"{len(access)} access entries; READER for {member} present")
