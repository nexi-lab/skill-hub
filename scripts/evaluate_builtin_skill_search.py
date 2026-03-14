#!/usr/bin/env python3
"""Upload legacy Nexus builtin skills and evaluate search quality/performance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import io
from pathlib import Path
from statistics import mean
import time
import zipfile

import httpx

from skillhub.legacy_skill import build_legacy_skill_package


@dataclass(frozen=True)
class QueryCase:
    package_name: str
    query: str


DEFAULT_QUERY_CASES = [
    QueryCase("pdf", "fill in a PDF form with fields"),
    QueryCase("pdf", "extract tables and text from a PDF document"),
    QueryCase("pdf", "merge or split PDF files"),
    QueryCase("xlsx", "recalculate formulas in an Excel spreadsheet"),
    QueryCase("xlsx", "build a financial model in excel with formulas"),
    QueryCase("xlsx", "modify a spreadsheet while preserving formulas"),
    QueryCase("docx", "edit a Word document with tracked changes"),
    QueryCase("docx", "analyze the contents of a .docx file"),
    QueryCase("docx", "add comments to a professional document"),
    QueryCase("pptx", "extract text from a PowerPoint presentation"),
    QueryCase("pptx", "work with slide layouts and speaker notes in pptx"),
    QueryCase("pptx", "modify presentation slides and notes"),
    QueryCase("internal-comms", "write a 3P update for leadership"),
    QueryCase("internal-comms", "draft an internal company newsletter"),
    QueryCase("internal-comms", "answer an FAQ for internal communications"),
    QueryCase("skill-creator", "create a new skill with specialized workflow guidance"),
    QueryCase("skill-creator", "update an existing skill package"),
    QueryCase("skill-creator", "design an effective skill with tool integrations"),
]


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _build_upload_plan(skill_dir: Path, publisher: str, version_suffix: str) -> list[tuple[str, bytes]]:
    archives = sorted(skill_dir.glob("*.skill"))
    plan: list[tuple[str, bytes]] = []
    for archive in archives:
        package = build_legacy_skill_package(
            archive,
            publisher=publisher,
            version=f"0.1.0-{version_suffix}",
        )
        plan.append((package.manifest.name, package.build_archive()))
    return plan


def _upload_package(client: httpx.Client, base_url: str, filename: str, archive_bytes: bytes) -> dict:
    response = client.post(
        f"{base_url.rstrip('/')}/v1/packages/upload",
        params={"filename": filename},
        headers={"content-type": "application/zip"},
        content=archive_bytes,
    )
    response.raise_for_status()
    return response.json()["package"]


def _verify_content(client: httpx.Client, base_url: str, publisher: str, name: str, version: str) -> None:
    response = client.get(
        f"{base_url.rstrip('/')}/v1/packages/{publisher}/{name}/{version}/content",
        params={"path": "SKILL.md"},
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("content"):
        raise ValueError(f"SKILL.md content missing for {publisher}/{name}@{version}")


def _verify_download(client: httpx.Client, base_url: str, publisher: str, name: str, version: str) -> list[str]:
    response = client.get(
        f"{base_url.rstrip('/')}/v1/packages/{publisher}/{name}/{version}/download"
    )
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return sorted(archive.namelist())


def _rank_for_package(hits: list[dict], publisher: str, package_name: str) -> int | None:
    expected_key = f"{publisher}/{package_name}"
    for index, hit in enumerate(hits, start=1):
        manifest = hit.get("package", {}).get("manifest", {})
        if f"{manifest.get('publisher')}/{manifest.get('name')}" == expected_key:
            return index
    return None


def _evaluate_mode(
    client: httpx.Client,
    base_url: str,
    publisher: str,
    mode: str,
    query_cases: list[QueryCase],
) -> dict[str, object]:
    latencies_ms: list[float] = []
    per_query: list[dict[str, object]] = []
    top1 = 0
    top3 = 0
    reciprocal_ranks: list[float] = []
    backends: set[str] = set()

    for case in query_cases:
        started = time.perf_counter()
        response = client.get(
            f"{base_url.rstrip('/')}/v1/packages/search",
            params={"q": case.query, "limit": 5, "mode": mode},
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        response.raise_for_status()
        payload = response.json()
        backends.add(str(payload.get("backend")))
        hits = payload.get("hits", [])
        rank = _rank_for_package(hits, publisher, case.package_name)
        if rank == 1:
            top1 += 1
        if rank is not None and rank <= 3:
            top3 += 1
            reciprocal_ranks.append(1.0 / rank)
        elif rank is not None:
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
        latencies_ms.append(elapsed_ms)
        per_query.append(
            {
                "query": case.query,
                "expected_package": case.package_name,
                "rank": rank,
                "latency_ms": elapsed_ms,
                "top_hit": (
                    hits[0]["package"]["manifest"]["name"] if hits else None
                ),
                "backend": payload.get("backend"),
            }
        )

    return {
        "mode": mode,
        "queries": len(query_cases),
        "hit_at_1": top1,
        "hit_at_1_pct": _percent(top1, len(query_cases)),
        "hit_at_3": top3,
        "hit_at_3_pct": _percent(top3, len(query_cases)),
        "mrr": round(mean(reciprocal_ranks), 3) if reciprocal_ranks else 0.0,
        "avg_latency_ms": round(mean(latencies_ms), 2) if latencies_ms else 0.0,
        "p95_latency_ms": _p95(latencies_ms),
        "max_latency_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
        "backends": sorted(backends),
        "per_query": per_query,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://35.223.194.208:8040")
    parser.add_argument(
        "--skill-dir",
        default="/Users/taofeng/nexus/data/skills",
        help="Directory containing legacy .skill archives",
    )
    parser.add_argument("--publisher", default="nexus-builtin")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["keyword", "semantic", "hybrid"],
    )
    parser.add_argument(
        "--report",
        default="",
        help="Optional JSON report path",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    version_suffix = "eval-" + started_at.strftime("%Y%m%d%H%M%S")
    upload_plan = _build_upload_plan(Path(args.skill_dir), args.publisher, version_suffix)
    if not upload_plan:
        raise SystemExit(f"No .skill archives found in {args.skill_dir}")

    uploaded: dict[str, dict[str, object]] = {}
    download_files: dict[str, list[str]] = {}
    with httpx.Client(timeout=120.0) as client:
        for package_name, archive_bytes in upload_plan:
            package = _upload_package(
                client,
                args.base_url,
                f"{package_name}-{version_suffix}.zip",
                archive_bytes,
            )
            uploaded[package_name] = package
            manifest = package["manifest"]
            _verify_content(
                client,
                args.base_url,
                manifest["publisher"],
                manifest["name"],
                manifest["version"],
            )
            download_files[package_name] = _verify_download(
                client,
                args.base_url,
                manifest["publisher"],
                manifest["name"],
                manifest["version"],
            )

        query_cases = [
            case for case in DEFAULT_QUERY_CASES if case.package_name in uploaded
        ]
        results_by_mode = {
            mode: _evaluate_mode(client, args.base_url, args.publisher, mode, query_cases)
            for mode in args.modes
        }

    report = {
        "base_url": args.base_url,
        "started_at": started_at.isoformat(),
        "publisher": args.publisher,
        "version_suffix": version_suffix,
        "uploaded_packages": {
            name: {
                "versioned_key": f"{pkg['manifest']['publisher']}/{pkg['manifest']['name']}@{pkg['manifest']['version']}",
                "artifact_files": pkg["artifact_files"],
                "download_files": download_files[name],
            }
            for name, pkg in uploaded.items()
        },
        "results_by_mode": results_by_mode,
    }

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
