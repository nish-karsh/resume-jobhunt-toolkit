"""Pre-built resume variants and offline TF-IDF matcher fallback."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Union

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.render_latex import render_resume, resume_to_plain_text
from src.resume_parser import ensure_profile, load_profile
from src.schemas import JobDescription, TailoredResume
from src.settings_loader import load_settings, project_root, resolve_path
from src.tailor import TailorError, tailor_resume

# Synthetic domain JDs used once at build time (one tailor call each).
DOMAIN_VARIANTS: dict[str, dict[str, Any]] = {
    "design_verification": {
        "title": "Design Verification Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "Design Verification Engineer — UVM, SystemVerilog, VCS, Questa, "
            "functional coverage, assertions, constrained-random testbenches, "
            "SOC verification, RTL verification, regression, debug, VIP, "
            "Cocotb, Python scripting for verification flows."
        ),
        "requirements": [
            "Strong UVM and SystemVerilog experience",
            "Functional coverage and assertion-based verification",
            "VCS or Questa simulation",
            "SOC/ASIC verification methodology",
            "Constrained-random testbench development",
        ],
        "keywords": [
            "uvm", "systemverilog", "verilog", "vcs", "questa", "verification",
            "dv", "coverage", "assertion", "testbench", "soc", "asic",
            "constrained-random", "regression", "debug", "vip", "cocotb", "python",
        ],
    },
    "rtl_design": {
        "title": "RTL Design Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "RTL Design Engineer — Verilog, SystemVerilog, RTL coding, "
            "microarchitecture, synthesis, lint, CDC, low-power design, "
            "AXI/APB/AMBA bus protocols, FPGA prototyping, timing closure support."
        ),
        "requirements": [
            "RTL design in Verilog/SystemVerilog",
            "Microarchitecture and logic design",
            "Synthesis and lint closure",
            "CDC/RDC methodology",
            "Bus protocols (AXI, APB, AMBA)",
        ],
        "keywords": [
            "rtl", "verilog", "systemverilog", "microarchitecture", "synthesis",
            "lint", "cdc", "rdc", "low-power", "axi", "apb", "amba", "fpga",
            "logic", "design", "soc", "asic",
        ],
    },
    "physical_design_sta": {
        "title": "Physical Design / STA Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "Physical Design and STA Engineer — Static Timing Analysis, PrimeTime, "
            "timing closure, synthesis, placement and routing, DFT, scan, "
            "crosstalk, clock transition, signoff, Tcl/Perl automation."
        ),
        "requirements": [
            "Static Timing Analysis (STA) with PrimeTime",
            "Timing closure and optimization",
            "Physical design flow knowledge",
            "Perl/Tcl scripting for EDA automation",
            "DFT and scan basics",
        ],
        "keywords": [
            "sta", "static", "timing", "primetime", "physical", "design",
            "synthesis", "placement", "routing", "dft", "scan", "crosstalk",
            "signoff", "perl", "tcl", "closure", "optimization",
        ],
    },
    "emulation": {
        "title": "Emulation Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "Emulation Engineer — Zebu, Palladium, Veloce, hardware emulation, "
            "transactor development, C++ modeling, UART/SPI protocols, "
            "HW/SW co-verification, testbench acceleration, debug on emulator."
        ),
        "requirements": [
            "Zebu or Palladium emulation platform experience",
            "Transactor and protocol modeling in C++",
            "HW/SW co-verification",
            "UART and serial protocol knowledge",
            "Emulation debug and regression",
        ],
        "keywords": [
            "emulation", "zebu", "palladium", "veloce", "transactor", "c++",
            "uart", "spi", "protocol", "hw/sw", "co-verification", "testbench",
            "acceleration", "debug", "modeling",
        ],
    },
    "embedded_firmware": {
        "title": "Embedded / Firmware Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "Embedded Firmware Engineer — STM32, ESP32, Arduino, C/C++, "
            "RTOS, IoT, sensors, PCB bring-up, RF modules, firmware development, "
            "hardware-in-the-loop, embedded Linux basics."
        ),
        "requirements": [
            "Embedded C/C++ firmware development",
            "STM32 / ESP32 microcontroller experience",
            "IoT connectivity and sensor integration",
            "PCB debug and hardware bring-up",
            "RTOS or bare-metal firmware",
        ],
        "keywords": [
            "embedded", "firmware", "stm32", "esp32", "arduino", "c", "c++",
            "rtos", "iot", "sensors", "pcb", "rf", "microcontroller",
            "hardware-in-the-loop", "bring-up",
        ],
    },
    "eda_software": {
        "title": "EDA Software Engineer",
        "company": "Target Domain Cache",
        "raw_text": (
            "EDA Software Engineer — Python, C++, Perl, tool development, "
            "automation scripts, CI/CD for chip design flows, API integration, "
            "data pipelines, Synopsys/Cadence tool flows, developer tooling."
        ),
        "requirements": [
            "Python and C++ for EDA tool development",
            "Perl/Tcl scripting for design flows",
            "Automation and regression infrastructure",
            "Synopsys or Cadence flow knowledge",
            "Software engineering best practices",
        ],
        "keywords": [
            "python", "c++", "perl", "eda", "automation", "scripting",
            "tool", "development", "ci/cd", "synopsys", "cadence", "api",
            "software", "engineering", "regression", "infrastructure",
        ],
    },
}

_BUILD_SLEEP_S = 2.0  # Respect ~40 rpm NIM rate limit between tailor calls.


def _domain_jd(domain_key: str, spec: dict[str, Any]) -> JobDescription:
    return JobDescription(
        raw_text=spec["raw_text"],
        title=spec["title"],
        company=spec.get("company", "Target Domain Cache"),
        location="India / Remote",
        seniority="Entry",
        requirements=list(spec.get("requirements", [])),
        keywords=list(spec.get("keywords", [])),
    )


def _variants_root(settings: dict[str, Any] | None = None) -> Path:
    cfg = settings or load_settings()
    return resolve_path("variants_dir", cfg)


def _manifest_path(variants_dir: Path) -> Path:
    return variants_dir / "manifest.json"


def _variant_dir(variants_dir: Path, domain_key: str) -> Path:
    return variants_dir / domain_key


def _index_text(tailored: TailoredResume, jd: JobDescription) -> str:
    """Plain-text blob for TF-IDF indexing (JD keywords + resume body)."""
    parts = [
        jd.raw_text,
        jd.title,
        " ".join(jd.requirements),
        " ".join(jd.keywords),
        resume_to_plain_text(tailored),
    ]
    return "\n".join(p for p in parts if p)


def build_variants(
    profile_path: Path | str | None = None,
    settings: dict[str, Any] | None = None,
    sleep_s: float = _BUILD_SLEEP_S,
) -> dict[str, Path]:
    """Build all cached variants via tailor_resume (one NIM call per domain)."""
    cfg = settings or load_settings()
    variants_dir = _variants_root(cfg)
    variants_dir.mkdir(parents=True, exist_ok=True)

    if profile_path:
        profile = load_profile(profile_path)
    else:
        profile = ensure_profile(cfg)

    manifest: dict[str, Any] = {"variants": {}, "built_at": ""}
    built: dict[str, Path] = {}

    for i, (domain_key, spec) in enumerate(DOMAIN_VARIANTS.items()):
        if i > 0 and sleep_s > 0:
            time.sleep(sleep_s)

        jd = _domain_jd(domain_key, spec)
        print(f"Building variant: {domain_key} ({jd.title})...", flush=True)

        tailored = tailor_resume(profile, jd, research=None)
        tailored.meta.model_used = f"{tailored.meta.model_used} (variant:{domain_key})"

        out_dir = _variant_dir(variants_dir, domain_key)
        basename = f"resume_{domain_key}"
        files = render_resume(
            tailored,
            out_dir,
            basename,
            formats=["pdf", "txt"],
            settings=cfg,
        )

        json_path = out_dir / "tailored.json"
        json_path.write_text(
            json.dumps(tailored.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        index_path = out_dir / "index.txt"
        index_path.write_text(_index_text(tailored, jd), encoding="utf-8")

        manifest["variants"][domain_key] = {
            "title": spec["title"],
            "dir": str(out_dir.relative_to(project_root())),
            "resume_txt": str(files["txt"].relative_to(project_root())),
            "resume_tex": str(files["tex"].relative_to(project_root())),
            "tailored_json": str(json_path.relative_to(project_root())),
            "index_txt": str(index_path.relative_to(project_root())),
        }
        built[domain_key] = out_dir
        print(f"  -> {out_dir}", flush=True)

    from datetime import datetime, timezone

    manifest["built_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _manifest_path(variants_dir).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return built


def _jd_text(jd_text_or_obj: Union[str, JobDescription]) -> str:
    if isinstance(jd_text_or_obj, JobDescription):
        parts = [
            jd_text_or_obj.raw_text,
            jd_text_or_obj.title,
            jd_text_or_obj.company,
            " ".join(jd_text_or_obj.requirements),
            " ".join(jd_text_or_obj.keywords),
        ]
        return "\n".join(p for p in parts if p)
    return str(jd_text_or_obj)


def _load_variant_corpus(variants_dir: Path) -> tuple[list[str], list[str], list[Path]]:
    """Return (domain_keys, index_texts, resume_txt_paths)."""
    keys: list[str] = []
    texts: list[str] = []
    paths: list[Path] = []

    manifest_file = _manifest_path(variants_dir)
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        for key, meta in manifest.get("variants", {}).items():
            index_rel = meta.get("index_txt", "")
            txt_rel = meta.get("resume_txt", "")
            index_path = project_root() / index_rel if index_rel else _variant_dir(variants_dir, key) / "index.txt"
            txt_path = project_root() / txt_rel if txt_rel else _variant_dir(variants_dir, key) / f"resume_{key}.txt"
            if index_path.exists():
                keys.append(key)
                texts.append(index_path.read_text(encoding="utf-8"))
                paths.append(txt_path if txt_path.exists() else index_path)
        if keys:
            return keys, texts, paths

    for domain_key in DOMAIN_VARIANTS:
        vdir = _variant_dir(variants_dir, domain_key)
        index_path = vdir / "index.txt"
        txt_path = vdir / f"resume_{domain_key}.txt"
        if index_path.exists():
            keys.append(domain_key)
            texts.append(index_path.read_text(encoding="utf-8"))
            paths.append(txt_path if txt_path.exists() else index_path)

    return keys, texts, paths


def match_variant(
    jd_text_or_obj: Union[str, JobDescription],
    settings: dict[str, Any] | None = None,
) -> tuple[str, Path, float]:
    """Offline TF-IDF match: return (variant_name, resume_txt_path, score 0-1)."""
    cfg = settings or load_settings()
    variants_dir = _variants_root(cfg)
    query = _jd_text(jd_text_or_obj)

    keys, corpus, paths = _load_variant_corpus(variants_dir)
    if not keys:
        raise FileNotFoundError(
            f"No cached variants in {variants_dir}. Run: python -m src.variant_library --build"
        )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_features=8000,
    )
    matrix = vectorizer.fit_transform(corpus + [query])
    query_vec = matrix[-1]
    corpus_matrix = matrix[:-1]
    scores = cosine_similarity(query_vec, corpus_matrix).flatten()

    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])
    return keys[best_idx], paths[best_idx], best_score


def load_variant_tailored(
    variant_name: str,
    settings: dict[str, Any] | None = None,
) -> TailoredResume:
    """Load a cached TailoredResume JSON for a variant domain key."""
    cfg = settings or load_settings()
    json_path = _variant_dir(_variants_root(cfg), variant_name) / "tailored.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Variant JSON not found: {json_path}")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return TailoredResume.from_dict(data)


def list_variants(settings: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return manifest entries for built variants."""
    cfg = settings or load_settings()
    manifest_file = _manifest_path(_variants_root(cfg))
    if not manifest_file.exists():
        return []
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for key, meta in manifest.get("variants", {}).items():
        out.append({"key": key, **meta})
    return out


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Resume variant library (build + offline match)")
    parser.add_argument("--build", action="store_true", help="Build all 6 cached variants via NIM")
    parser.add_argument("--match", type=str, default="", help="Test TF-IDF match against JD text")
    parser.add_argument("--list", action="store_true", help="List built variants")
    args = parser.parse_args()

    if args.build:
        try:
            build_variants()
            print("All variants built successfully.")
            return 0
        except TailorError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.match:
        name, path, score = match_variant(args.match)
        print(f"variant: {name}")
        print(f"path: {path}")
        print(f"score: {score:.4f}")
        return 0

    if args.list:
        for entry in list_variants():
            print(f"- {entry['key']}: {entry.get('title', '')}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
