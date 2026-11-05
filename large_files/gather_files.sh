#!/usr/bin/env bash
# Script for gathering large inputs required by Talos.
# Output file names created/expected by this script match the defaults in `nextflow.config`.
set -euo pipefail

TMX=$(command -v tmux)
POLL_INTERVAL=1
SESSION_NAME="download_manager"
WINDOW_NAME="Downloads"
TMX_WINDOW_ID=""
declare -a DOWNLOAD_TARGETS=()
declare -i DOWNLOAD_FAILURES=0
DISABLE_TMUX="${TALOS_DISABLE_TMUX:-0}"

if [ -n "${SLURM_JOB_ID:-}" ]; then
  DISABLE_TMUX=1
fi

if [ "$DISABLE_TMUX" != "1" ] && [ -n "$TMX" ] && [ -z "${TMUX:-}" ]; then
  # tmux installed, but not in a tmux session. Restart in tmux using bash, not sh.
  # If tmux startup fails, continue in the current shell instead of exiting immediately.
  if tmux new-session -d -s "$SESSION_NAME" bash "$0" "$@"; then
    tmux attach-session -t "$SESSION_NAME"
    exit 0
  fi
  echo "[WARN] Failed to start tmux session; continuing in the current shell."
  TMX=""
fi

cleanup() {
  echo "[INFO] Caught exit signal. Cleaning up..."
  CURRENT_PGID=$(ps -o pgid= -p $$ | tr -d '[:space:]')
  pkill -SIGTERM -g "$CURRENT_PGID" -f curl

  if [ -z "${TMX:-}" ]; then
	wait || true
  else
    # Kill the tmux window we created for the downloads
    if "$TMX" list-windows | grep -q "$WINDOW_NAME"; then
      $TMX kill-window -t "$TMX_WINDOW_ID"
    fi
  fi
  echo "[INFO] Cleanup complete."
  exit 0
}

start_download() {
  local url="$1"
  local output="${2:-}"
  local banner="${3:-}"

  if [ -z "$output" ]; then
    output=$(basename "$url")
  fi
  if [ -z "$banner" ]; then
    banner="Downloading [$output]"
  fi
  # Use a temporary partial file so incomplete downloads never appear at the final path.
  # We keep resume ability by always resuming (-C -) against the .part file and only mv to final name on success.
  local final="$output"
  local part_file="${final}.part"

  # Record expected final file for later summary (avoid duplicates)
  DOWNLOAD_TARGETS+=("$final")

  # If the final file already exists, skip (assume complete). Could add checksum logic here if desired.
  if [ -f "$final" ]; then
    echo "[INFO] $final already present, skipping download."
    return 0
  fi

  # Banner shown once per (re)attempt.
  # curl exit codes: 18 = partial file; we keep part_file for later resume.
  # On success (exit 0) we atomically mv into place.
  # NOTE: All internal $ variables are escaped (\$) so they are evaluated when the command runs, not now.
  local script_name="$(basename "$0")"
  local cmd="echo \"$banner\"; echo; curl -C - -# -L --fail -o \"$part_file\" \"$url\" && mv -f \"$part_file\" \"$final\" || { rc=\$?; if [ \"\$rc\" -ne 0 ]; then echo \"[WARN] $final Download failed for (exit \${rc}). Restart ${script_name} to gracefully resume download.\"; fi; }"
  if [ -z "${TMX:-}" ] || [ "$DISABLE_TMUX" = "1" ]; then
     ( eval "$cmd" ) &
  else
    echo "[JOB START] Starting download for: $url to $output."
    if [ -z "$TMX_WINDOW_ID" ]; then
      TMX_WINDOW_ID=$($TMX new-window -P -n "$WINDOW_NAME" "$cmd")
    else
      $TMX split-window -v -t "$TMX_WINDOW_ID" "$cmd"
      $TMX select-layout -t "$TMX_WINDOW_ID" even-vertical
    fi
  fi
}

await() {
  if [ -z "${TMX:-}" ] || [ "$DISABLE_TMUX" = "1" ]; then
    local pid
    local rc
    for pid in $(jobs -p); do
      if ! wait "$pid"; then
        rc=$?
        DOWNLOAD_FAILURES+=1
        echo "[WARN] Background download job ${pid} failed (exit ${rc})."
      fi
    done
    return 0
  else
    # No downloads were started in tmux — nothing to wait on.
    if [ -z "$TMX_WINDOW_ID" ]; then
      return 0
    fi
  last_pane_count=-1
    while true; do
      pane_count=$($TMX list-panes -t "$TMX_WINDOW_ID" 2>/dev/null | wc -l)
      if [ "$last_pane_count" != "$pane_count" ]; then
        $TMX select-layout -t "$TMX_WINDOW_ID" even-vertical
        last_pane_count=$pane_count
      fi
      if [ "$pane_count" = 0 ]; then
        break;
      fi
      sleep "$POLL_INTERVAL"
    done
  fi
}

trap cleanup SIGINT SIGTERM

for required_cmd in curl gunzip gzip sed date; do
  if ! command -v "$required_cmd" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $required_cmd"
    exit 1
  fi
done

# Echtvar-encoded gnomAD 4.1 population frequencies - this is a big one (~6GB) so it's started early and backgrounded
ECHTVAR_FILE="gnomad_4.1_region_merged_GRCh38_whole_genome"
start_download https://zenodo.org/records/15222100/files/gnomad_4.1_region_merged_GRCh38_whole_genome?download=1 "${ECHTVAR_FILE}" "\
Downloading Echtvar from https://zenodo.org/records/15222100"

# Monarch phenotype DB - another large download. 17GB decompressed
COMPRESSED_PHENIO="phenio.db.gz"
DECOMPRESSED_PHENIO="phenio.db"
if [ ! -f "${DECOMPRESSED_PHENIO}" ]; then
  echo "[INFO] phenio.db not found, downloading..."
  start_download https://data.monarchinitiative.org/monarch-kg/latest/phenio.db.gz
else
  echo "[INFO] phenio.db already exists, skipping download."
fi

# GRCh38 reference genome
GRCh38="ref.fa.gz"
GRCh38_decompressed="ref.fa"
# if it doesn't exist, download it
if [ ! -f "${GRCh38_decompressed}" ]; then
  echo "[INFO] compressed ref.fa not found, attempting download..."
    GRCh38_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz"
    start_download ${GRCh38_URL} ${GRCh38} "Downloading compressed GRCh38 reference genome from UCSC"
else
  echo "[INFO] ${GRCh38_decompressed} already exists, skipping download."
fi

# MANE gene data
start_download https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/release_1.5/MANE.GRCh38.v1.5.summary.txt.gz

# Ensembl GFF3 data
GFF3_ORIGINAL="Homo_sapiens.GRCh38.116.chr.gff3.gz"
GFF3_chrM_RENAMED="Homo_sapiens.GRCh38.116.MTtoM.gff3.gz"
start_download https://ftp.ensembl.org/pub/release-116/vertebrates/gff3/homo_sapiens/Homo_sapiens.GRCh38.116.chr.gff3.gz

# Jax lab file for phenotype matching
start_download https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-02-16/hp.obo

start_download https://github.com/obophenotype/human-phenotype-ontology/releases/download/v2026-02-16/genes_to_phenotype.txt

# mitochondrial annotations
start_download https://www.mitomap.org/downloads/mitotip_scores.txt

start_download "https://mitimpact.mcb2lab.org/cdn/nAPOGEE_v1.0.0.txt.zip"

start_download "https://mitimpact.mcb2lab.org/cdn/MitImpact_db_3.1.3.txt.zip"

# AlphaMissense raw data
AM="AlphaMissense_hg38.tsv.gz"
start_download "https://zenodo.org/records/8208688/files/AlphaMissense_hg38.tsv.gz?download=1" "${AM}"

await

#if compressed exists, but decompressed doesn't, gunzip it
if [ ! -f "${GRCh38_decompressed}" ] && [ -f "${GRCh38}" ]; then
    echo "Decompressing reference Fasta"
    gunzip ${GRCh38}
fi

# same for the phenio files
if [ ! -f "${DECOMPRESSED_PHENIO}" ] && [ -f "${COMPRESSED_PHENIO}" ]; then
    echo "Decompressing Phenio.db"
    gunzip ${COMPRESSED_PHENIO}
fi

# rinse the Ensembl GFF3 file through a chrMT -> chrM rename
if [ ! -f "${GFF3_chrM_RENAMED}" ] && [ -f "${GFF3_ORIGINAL}" ]; then
    echo "Renaming MT to M in ensembl GFF3 file"
    gunzip -c "${GFF3_ORIGINAL}" | sed 's/^MT/M/' | gzip > "${GFF3_chrM_RENAMED}"
fi

if [ -f "${GRCh38_decompressed}" ] && [ ! -f "${GRCh38_decompressed}.fai" ]; then
  if command -v samtools >/dev/null 2>&1; then
    echo "Indexing reference Fasta with samtools faidx"
    samtools faidx "${GRCh38_decompressed}"
  else
    echo "[WARN] samtools not found; skipping ${GRCh38_decompressed}.fai generation"
  fi
fi

# Final status summary
summary_fail=0
script_name_summary="$(basename "$0")"
for target in "${DOWNLOAD_TARGETS[@]}"; do
  if [ ! -f "$target" ]; then
    echo "[MISSING] $target"
    summary_fail=$((summary_fail+1))
  fi
done

if [ $summary_fail -eq 0 ]; then
  echo "[SUCCESS] All ${#DOWNLOAD_TARGETS[@]} downloads completed successfully."
else
  echo "[SUMMARY] $summary_fail of ${#DOWNLOAD_TARGETS[@]} downloads missing. Restart ${script_name_summary} to gracefully resume."
fi

if [ $DOWNLOAD_FAILURES -gt 0 ]; then
  echo "[SUMMARY] ${DOWNLOAD_FAILURES} background download job(s) returned a non-zero exit code."
fi
