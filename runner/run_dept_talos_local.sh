#!/usr/bin/env bash

set -euo pipefail
umask 002

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
RUN_DIR="${RUN_DIR:-${SCRIPT_DIR}}"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
CONDA_ENV="${CONDA_ENV:-/faststorage/project/reanalyses_auh/env/talos2_env}"

TALOS_INPUT_TSV="${TALOS_INPUT_TSV:-${RUN_DIR}/talos_input.tsv}"
TALOS_OUTPUT_DIR="${TALOS_OUTPUT_DIR:-${RUN_DIR}/cohort_outputs}"
PROCESSED_ANNOTATIONS_DIR="${PROCESSED_ANNOTATIONS_DIR:-${RUN_DIR}/processed_annotations}"
TALOS_NEXTFLOW_CONFIG="${TALOS_NEXTFLOW_CONFIG:-${RUN_DIR}/config/dept_local.config}"
SPLICEAI_MODE="${SPLICEAI_MODE:-precomputed}"
SPLICEAI_VCF="${SPLICEAI_VCF:-/faststorage/project/reanalyses_auh/resources/spliceai_scores_KGA_AUH_GRCh_38_Homo_sapiens_converted.vcf.gz}"
FASTSPLICEAI_BIN="${FASTSPLICEAI_BIN:-/faststorage/project/reanalyses_auh/env/fastspliceai_pip/bin/spliceai}"
FASTSPLICEAI_REFERENCE="${FASTSPLICEAI_REFERENCE:-}"
FASTSPLICEAI_ANNOTATION="${FASTSPLICEAI_ANNOTATION:-}"
FASTSPLICEAI_CACHE="${FASTSPLICEAI_CACHE:-}"
FASTSPLICEAI_NEXTFLOW_CONFIG="${FASTSPLICEAI_NEXTFLOW_CONFIG:-${REPO_DIR}/runner/talos_fastspliceai.config}"
FASTSPLICEAI_QUEUE="${FASTSPLICEAI_QUEUE:-gpu-l40s,gpu-h200}"
FASTSPLICEAI_CLUSTER_OPTIONS="${FASTSPLICEAI_CLUSTER_OPTIONS:---account=reanalyses_auh --gpus=1}"
FASTSPLICEAI_CPUS="${FASTSPLICEAI_CPUS:-6}"
FASTSPLICEAI_MEM="${FASTSPLICEAI_MEM:-16G}"
FASTSPLICEAI_TIME="${FASTSPLICEAI_TIME:-08:00:00}"
RESUME="${RESUME:-true}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-dir) RUN_DIR="$2"; shift 2 ;;
        --repo-dir) REPO_DIR="$2"; shift 2 ;;
        --conda-env) CONDA_ENV="$2"; shift 2 ;;
        --input-tsv) TALOS_INPUT_TSV="$2"; shift 2 ;;
        --output-dir) TALOS_OUTPUT_DIR="$2"; shift 2 ;;
        --processed-annotations) PROCESSED_ANNOTATIONS_DIR="$2"; shift 2 ;;
        --nextflow-config) TALOS_NEXTFLOW_CONFIG="$2"; shift 2 ;;
        --spliceai-mode) SPLICEAI_MODE="$2"; shift 2 ;;
        --spliceai-vcf) SPLICEAI_VCF="$2"; shift 2 ;;
        --fastspliceai-bin) FASTSPLICEAI_BIN="$2"; shift 2 ;;
        --fastspliceai-reference) FASTSPLICEAI_REFERENCE="$2"; shift 2 ;;
        --fastspliceai-annotation) FASTSPLICEAI_ANNOTATION="$2"; shift 2 ;;
        --fastspliceai-cache) FASTSPLICEAI_CACHE="$2"; shift 2 ;;
        --fastspliceai-nextflow-config) FASTSPLICEAI_NEXTFLOW_CONFIG="$2"; shift 2 ;;
        --fastspliceai-queue) FASTSPLICEAI_QUEUE="$2"; shift 2 ;;
        --fastspliceai-cluster-options) FASTSPLICEAI_CLUSTER_OPTIONS="$2"; shift 2 ;;
        --fastspliceai-cpus) FASTSPLICEAI_CPUS="$2"; shift 2 ;;
        --fastspliceai-mem) FASTSPLICEAI_MEM="$2"; shift 2 ;;
        --fastspliceai-time) FASTSPLICEAI_TIME="$2"; shift 2 ;;
        --resume) RESUME="$2"; shift 2 ;;
        -h|--help)
            cat <<'EOF'
Usage: bash run_dept_talos_local.sh [options]

Options:
  --run-dir PATH
  --repo-dir PATH
  --conda-env NAME_OR_PREFIX
  --input-tsv PATH
  --output-dir PATH
  --processed-annotations PATH
  --nextflow-config PATH
  --spliceai-mode precomputed|fastspliceai|fastspliceai_cache|disabled
  --spliceai-vcf PATH
  --fastspliceai-bin PATH
  --fastspliceai-reference PATH
  --fastspliceai-annotation PATH_OR_GRCH38
  --fastspliceai-cache PATH
  --fastspliceai-nextflow-config PATH
  --fastspliceai-queue PARTITION
  --fastspliceai-cluster-options OPTIONS
  --fastspliceai-cpus N
  --fastspliceai-mem SIZE
  --fastspliceai-time HH:MM:SS
  --resume true|false
EOF
            exit 0
            ;;
        *) echo "[ERROR] Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ "${RUN_DIR}" != /* ]]; then
    RUN_DIR="$(cd "${RUN_DIR}" && pwd -P)"
fi

resolve_run_path() {
    local value="$1"
    if [[ -z "${value}" || "${value}" == /* ]]; then
        printf '%s' "${value}"
    else
        printf '%s/%s' "${RUN_DIR}" "${value}"
    fi
}

SPLICEAI_VCF="$(resolve_run_path "${SPLICEAI_VCF}")"
FASTSPLICEAI_BIN="$(resolve_run_path "${FASTSPLICEAI_BIN}")"
FASTSPLICEAI_REFERENCE="$(resolve_run_path "${FASTSPLICEAI_REFERENCE}")"
FASTSPLICEAI_CACHE="$(resolve_run_path "${FASTSPLICEAI_CACHE}")"
if [[ -z "${FASTSPLICEAI_ANNOTATION}" ]]; then
    FASTSPLICEAI_ANNOTATION="${REPO_DIR}/resources/grch38_MANE_v1.5.txt"
elif [[ "${FASTSPLICEAI_ANNOTATION}" != "grch37" && "${FASTSPLICEAI_ANNOTATION}" != "grch38" ]]; then
    FASTSPLICEAI_ANNOTATION="$(resolve_run_path "${FASTSPLICEAI_ANNOTATION}")"
fi

case "${SPLICEAI_MODE}" in
precomputed)
    if [[ -z "${SPLICEAI_VCF}" ]]; then
        echo "[ERROR] --spliceai-vcf is required when --spliceai-mode precomputed" >&2
        exit 1
    fi
    if [[ ! -e "${SPLICEAI_VCF}" ]]; then
        echo "[ERROR] Missing SpliceAI VCF: ${SPLICEAI_VCF}" >&2
        exit 1
    fi
    ;;
fastspliceai|fastspliceai_cache)
    if [[ ! -x "${FASTSPLICEAI_BIN}" ]]; then
        echo "[ERROR] FastSpliceAI executable is missing: ${FASTSPLICEAI_BIN}" >&2
        exit 1
    fi
    if [[ -z "${FASTSPLICEAI_REFERENCE}" || ! -f "${FASTSPLICEAI_REFERENCE}" || ! -f "${FASTSPLICEAI_REFERENCE}.fai" ]]; then
        echo "[ERROR] --fastspliceai-reference and its .fai index are required" >&2
        exit 1
    fi
    if [[ ! -f "${FASTSPLICEAI_NEXTFLOW_CONFIG}" ]]; then
        echo "[ERROR] FastSpliceAI Nextflow config is missing: ${FASTSPLICEAI_NEXTFLOW_CONFIG}" >&2
        exit 1
    fi
    if [[ "${SPLICEAI_MODE}" == "fastspliceai_cache" && -z "${FASTSPLICEAI_CACHE}" ]]; then
        echo "[ERROR] --fastspliceai-cache is required when --spliceai-mode fastspliceai_cache" >&2
        exit 1
    fi
    ;;
disabled) ;;
*) echo "[ERROR] Invalid --spliceai-mode: ${SPLICEAI_MODE}" >&2; exit 1 ;;
esac

mkdir -p "${TALOS_OUTPUT_DIR}" "${RUN_DIR}/work" "${RUN_DIR}/logs"

if [[ -d "${CONDA_ENV}" && -x "${CONDA_ENV}/bin/nextflow" ]]; then
    export PATH="${CONDA_ENV}/bin:${PATH}"
else
    if [[ -n "${CONDA_EXE:-}" ]]; then
        CONDA_BIN="${CONDA_EXE}"
    elif command -v conda >/dev/null 2>&1; then
        CONDA_BIN="$(command -v conda)"
    else
        echo "[ERROR] Could not find conda on PATH." >&2
        exit 1
    fi

    CONDA_BASE="$("${CONDA_BIN}" info --base)"
    CONDA_SH="${CONDA_BASE}/etc/profile.d/conda.sh"
    if [[ ! -f "${CONDA_SH}" ]]; then
        echo "[ERROR] Conda initialization script not found: ${CONDA_SH}" >&2
        exit 1
    fi

    source "${CONDA_SH}"
    conda activate "${CONDA_ENV}"
fi

export PYTHONPATH="${REPO_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
export FASTSPLICEAI_BIN FASTSPLICEAI_REFERENCE FASTSPLICEAI_ANNOTATION FASTSPLICEAI_CACHE FASTSPLICEAI_QUEUE FASTSPLICEAI_CLUSTER_OPTIONS
export FASTSPLICEAI_CPUS FASTSPLICEAI_MEM FASTSPLICEAI_TIME
export NXF_HOME="${NXF_HOME:-${RUN_DIR}/.nextflow-local}"
export NXF_PLUGINS_DIR="${NXF_PLUGINS_DIR:-${NXF_HOME}/plugins}"
mkdir -p "${NXF_HOME}" "${NXF_PLUGINS_DIR}"

cd "${RUN_DIR}"

nextflow_configs=(
    -c "${REPO_DIR}/nextflow.config"
    -c "${TALOS_NEXTFLOW_CONFIG}"
)
nextflow_args=(
    run "${REPO_DIR}/main.nf"
    --input_tsv "${TALOS_INPUT_TSV}"
    --processed_annotations "${PROCESSED_ANNOTATIONS_DIR}"
    --spliceai_mode "${SPLICEAI_MODE}"
    -output-dir "${TALOS_OUTPUT_DIR}"
)

if [[ "${SPLICEAI_MODE}" == "precomputed" ]]; then
    nextflow_args+=(--spliceai_vcf "${SPLICEAI_VCF}")
fi

if [[ "${SPLICEAI_MODE}" == "fastspliceai" || "${SPLICEAI_MODE}" == "fastspliceai_cache" ]]; then
    nextflow_configs+=(-c "${FASTSPLICEAI_NEXTFLOW_CONFIG}")
    nextflow_args+=(--fastspliceai_bin "${FASTSPLICEAI_BIN}" --fastspliceai_reference "${FASTSPLICEAI_REFERENCE}" --fastspliceai_annotation "${FASTSPLICEAI_ANNOTATION}")
    if [[ "${SPLICEAI_MODE}" == "fastspliceai_cache" ]]; then
        nextflow_args+=(--fastspliceai_cache "${FASTSPLICEAI_CACHE}")
    fi
fi

if [[ "${RESUME}" == "true" ]]; then
    nextflow_args+=(-resume)
fi

exec nextflow "${nextflow_configs[@]}" "${nextflow_args[@]}"
