import argparse
import json
import tempfile
from pathlib import Path
from . import Archive
from .codec import pack
from .samples import build_legacy


def main():
    parser = argparse.ArgumentParser(description="Exact conservative grid archive")
    parser.add_argument("command", choices=["demo"])
    parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gridarchive-demo-") as directory:
        path = str(Path(directory) / "archive.sqlite")
        ids = build_legacy(path)
        with Archive(path) as archive:
            original = archive.read_result(ids["job"])
            rerun = archive.run_job(ids["job"])
            assert original["result"] == rerun["result"]
            assert rerun["result"]["allocated"]["small"] == 3
            assert rerun["result"]["allocated"]["large"] == 9
            assert archive.head("source") == ids["new_source"]
            print(json.dumps(pack({
                "bindings": ids,
                "historical": rerun,
                "current": archive.read_result(ids["new_job"]),
                "self_crossing": archive.read_result(ids["bow_job"]),
                "source_head": archive.head("source"),
            }), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
