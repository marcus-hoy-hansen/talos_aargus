# TALOS AARGUS TEST RUNNER

Browser-based test runner for TALOS AARGUS workflows:

- upload or load an Excel `.xlsx`
- edit rows and write a new Excel `.xlsx`
- preview rows
- edit `runner.config`
- run resource download, Talos preparation, preflight, and full TALOS panes

The default project is the tracked `synthetic_one_proband_two_variants/`
fixture. It contains a one-proband Excel sheet and two reference-validated raw
VCF calls. Results generated from that fixture are ignored by Git.

## Run

If `reflex` is available in the active environment:

```bash
./run_reflex_excel_runner.sh
```

If Reflex is installed in a named conda environment:

```bash
REFLEX_CONDA_ENV=my_env ./run_reflex_excel_runner.sh
```

If Reflex is installed in a conda prefix:

```bash
REFLEX_CONDA_PREFIX=/path/to/env ./run_reflex_excel_runner.sh
```

Run this on the cluster frontend/login node, not inside a compute allocation.
The command defaults to frontend port `3100` and backend port `8100`.

Then open:

```text
http://localhost:3100
```

If opening from your laptop, tunnel the same ports:

```bash
ssh -L 3100:localhost:3100 -L 8100:localhost:8100 <user>@<frontend-host>
```

Extra Reflex flags are passed through. For example:

```bash
REFLEX_CONDA_ENV=talos_env ./run_reflex_excel_runner.sh --single-port
```

## Dependency

The app requires Reflex and `openpyxl`:

```bash
pip install -r requirements.txt
```

or:

```bash
conda install -c conda-forge reflex openpyxl
```

## Code layout

```text
reflex_excel_runner.py  Reflex app entry point
state.py               App state and event handlers
views.py               Reflex UI components
excel_io.py            Excel read/write helpers
runner.py              bash/sbatch command construction and execution
config_io.py           config save/load
paths.py               Shared paths and constants
```

## runner.config

`runner.config` is a flat bash-like file:

```bash
PREFLIGHT_DEFAULT_PROJECT_DIR=/path/to/project
PREFLIGHT_SAMPLELIST_FILENAME=samplelist.xlsx
PREFLIGHT_SOURCE_VCF_FOLDERS=/path/a|/path/b
PREFLIGHT_DEPARTMENT=DEPT
PREFLIGHT_INPUTS_DIR=inputs
PREFLIGHT_OUTPUTS_DIR=outputs
PREFLIGHT_WORK_DIR=work
PREFLIGHT_LOG_DIR=logs
PREFLIGHT_NEXTFLOW_LOG=logs/.nextflow.log
PREFLIGHT_SYMLINK_DIR=VCF_symlinks
PREFLIGHT_TALOS_COHORT=DEPT
PREFLIGHT_FAMILY_MERGE_ENABLED=false
PREFLIGHT_RESUME=true

TALOS_TOOL_DIR=/path/to/talos_aargus
TALOS_INPUT_TSV=outputs/talos_input.tsv
TALOS_OUTPUT_DIR=cohort_outputs
TALOS_PROCESSED_ANNOTATIONS=/path/to/processed_annotations
TALOS_NEXTFLOW_CONFIG=config/dept_local.config
TALOS_CONDA_ENV=/faststorage/project/reanalyses_auh/env/talos2_env
TALOS_SPLICEAI_ENABLED=true
TALOS_SPLICEAI_VCF=/faststorage/project/reanalyses_auh/resources/spliceai_scores_KGA_AUH_GRCh_38_Homo_sapiens_converted.vcf.gz
TALOS_RESUME=true
```

The Preflight pane has one project path. It defaults to
`PREFLIGHT_DEFAULT_PROJECT_DIR`, and all `inputs/`, `outputs/`, `work/`,
`logs/`, and `.nextflow.log` paths are derived from the settings above. The
`Choose project` dialog is a one-session override and never writes to
`runner.config`. Selecting a project there also updates the TALOS project.

All department and cohort values are configuration, not code. Change them in the
Config pane or directly in `runner.config` for a different project.

## Panes

`Import` loads an `.xlsx` file, displays the content as tab-delimited text, and
keeps the preview table in sync with that editor. The first line is the header.
Rows can be edited directly, a blank row can be appended, a 1-based data row can
be deleted, and the edited table can be saved as a new `.xlsx` file.

`Resources` runs the Talos `large_files/download_resources_slurm.sh` script with
plain `bash` and displays output.

`Preparation` runs from the Talos repo directory:

```bash
cd /path/to/talos_aargus
/faststorage/project/reanalyses_auh/env/talos2_env/bin/nextflow -c nextflow.config run preparation.nf \
  --processed_annotations processed_annotations \
  --large_files large_files
```

The working directory, shared environment prefix, and the two output/input
folder names are loaded from `runner.config` and can be edited in the pane
before running.

`Preflight` writes and submits `<project>/logs/talos_preflight.sbatch`. The
sbatch job first runs `prepare_dept_preflight_inputs.py` for the selected Excel
file, then runs `run_dept_preflight_local.sh` with project-specific input,
output, work, and log paths. Preflight SpliceAI annotation is off by default,
but the stable output filename remains `cohort_merged.vcf.gz`. Source VCF
folders are optional overrides; enter one folder per line, or leave the field
empty for parser auto-detection.

Family VCF construction is also off by default. The cohort is merged directly
from prepared individual VCFs, retaining the existing missing-to-reference
parent genotype convention. Set `PREFLIGHT_FAMILY_MERGE_ENABLED=true` in
`runner.config` when per-proband family VCF construction is required.

VCF source selection is deliberately simple:

1. `Source VCF folder(s)` in the pane wins. Multiple folders can be entered, one
   per line.
2. If no source folder is entered and the selected project has local
   `source_vcfs/`, that folder is used. This is the synthetic-fixture path.
3. If neither is set, `PREFLIGHT_DEPARTMENT` is used to search the standard
   `/faststorage/project/MomaDiagnosticSamples-<department>` tree.

There is no automatic department guessing from the project folder name.
Use `Refresh log` to reload the Slurm `.out` file, which contains the Nextflow
screen output. Slurm `.err` content and the tail of `.nextflow.log` are shown
in separate boxes below it.

`TALOS` writes and submits `<project>/logs/talos_full.sbatch`. It does not
rebuild the TALOS command itself; it calls `run_dept_talos_local.sh` with
environment overrides for the selected project folder, TALOS tool folder, input
TSV, output folder, processed annotations, Nextflow config, conda environment,
SpliceAI mode, and resume setting. By default the input TSV is the
preflight output `outputs/talos_input.tsv`.

Selecting a project in the Preflight pane also updates the TALOS project folder,
so a preflighted project can be carried directly into the TALOS pane. The TALOS
project field remains editable afterward.

`SpliceAI mode` controls the main TALOS annotation step, not the preflight
step. Select `precomputed`, `fastspliceai`, `fastspliceai_cache`, or
`disabled`. The FastSpliceAI executable, reference, cache VCF, and GPU
resources are loaded from `runner.config`. Precomputed mode makes the submitted
command include:

```bash
bash run_dept_talos_local.sh \
  --spliceai-mode precomputed \
  --spliceai-vcf /path/to/spliceai.vcf.gz
```

Wrapper environment variables are still accepted for backward compatibility,
but the runner writes explicit command-line arguments.
