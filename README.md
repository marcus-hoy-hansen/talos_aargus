# Talos Aargus

[![Docs](https://img.shields.io/badge/docs-populationgenomics.github.io%2Ftalos-blue)](https://populationgenomics.github.io/talos/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Test](https://github.com/populationgenomics/automated-interpretation-pipeline/actions/workflows/test.yaml/badge.svg)

This repository is an Aarhus University Hospital extension of the Talos workflow.

It keeps the Talos v11 TSV-driven analysis model, but adds an AUH-oriented runtime
and preflight layer:

- native-first execution without requiring Docker
- optional Apptainer packaging
- standalone `preflight/` workflow for singleton, duo, and trio VCF preparation
- In-house resource wiring for common variants, variant artefacts, and splicing variants

## Part 1. AUH Extended Pipeline

### Overview

The AUH extension is intended to support:

- local or cluster execution with explicit runtime paths
- preflight preparation of family VCFs before Talos
- Slurm-friendly bundle generation for full end-to-end runs
- optional Apptainer execution with the tested Talos runtime baked into the image

The main components are:

- `preparation.nf`
  Creates processed Talos annotations such as ClinVar, PM5, PanelApp, and encoded annotation resources
- `main.nf`
  Runs annotation plus Talos prioritisation from a TSV input file
- `talos_only.nf`
  Runs Talos only on previously annotated inputs
- `preflight/main.nf`
  Standalone AUH preflight workflow for manifest-driven family preparation

### Runtime Layout

Expected local structure:

- `large_files/`
  Downloaded static reference resources
- `processed_annotations/`
  Prepared Talos annotation outputs from `preparation.nf`
- `/faststorage/project/reanalyses_auh/env/talos2_env/bin`
  Shared AUH runtime path used by the preflight layer and local example scripts,
  including `nextflow`
- `../../../resources/`
  Shared AUH sibling resource folder for common-dbSNP and SpliceAI

### Install

Requirements:

- [Nextflow](https://www.nextflow.io/docs/latest/install.html)
- Java
- Python 3.10 or 3.11
- `bcftools`, `tabix`, `bgzip`, `samtools`, `wget`

For a shared conda-based setup:

```bash
bash scripts/install_talos_env.sh
```

### Prepare Static Resources

Download the larger static resource set:

```bash
bash large_files/gather_files.sh
```

On Slurm systems, a batch wrapper is also provided:

```bash
sbatch large_files/download_resources_slurm.sh
```

Then prepare Talos processed annotations:

```bash
nextflow -c nextflow.config run preparation.nf \
  --processed_annotations processed_annotations \
  --large_files large_files
```

### Workflow Smoke Test

The repository includes a smoke-test TSV for the Talos v11 input model:

```bash
nextflow -c nextflow.config run main.nf \
  --input_tsv nextflow/inputs/test.tsv \
  --processed_annotations processed_annotations \
  -output-dir nextflow_output
```

If you want to test the Apptainer path instead:

```bash
bash build_apptainer_frontend.sh
bash run_nextflow_example_apptainer.sh
```

### SpliceAI Modes

The main workflow supports four explicit SpliceAI modes:

- `precomputed` (default): copy `INFO/SpliceAI` from an indexed resource VCF
- `fastspliceai`: compute scores once on the normalized collective cohort VCF
- `fastspliceai_cache`: compute only normalized alleles absent from a shared cache
- `disabled`: do not add SpliceAI annotation

Precomputed lookup remains the standard native run:

```bash
nextflow -c nextflow.config run main.nf \
  --input_tsv /path/to/talos_input.tsv \
  --processed_annotations processed_annotations \
  --spliceai_mode precomputed \
  --spliceai_vcf /path/to/spliceai_scores.vcf.gz \
  -output-dir /path/to/talos_outputs
```

Direct `fastspliceai` mode is submitted as one GPU process on the normalized
collective VCF, before it is split for the ordinary CPU annotation tasks. Add
the GPU process configuration and provide the executable and reference:

FastSpliceAI is deliberately kept as a separate Git checkout from
[`MOMA-AUH/FastSpliceAI`](https://github.com/MOMA-AUH/FastSpliceAI), with its
own shared environment. It is not vendored into `talos_aargus` and is not part
of this repository's Git history. The workflow only calls the configured
`fastspliceai_bin` executable.

```bash
nextflow \
  -c nextflow.config \
  -c runner/talos_fastspliceai.config \
  run main.nf \
  --input_tsv /path/to/talos_input.tsv \
  --processed_annotations processed_annotations \
  --spliceai_mode fastspliceai \
  --fastspliceai_bin /path/to/fastspliceai_pip/bin/spliceai \
  --fastspliceai_reference large_files/ref.fa \
  -output-dir /path/to/talos_outputs
```

For repeated cohorts, use a shared genotype-free VCF cache. It records every
evaluated normalized allele, including alleles without a useful score. Cache
misses are scored, merged under a file lock, and `INFO/SpliceAI` is then copied
onto the full cohort VCF without changing genotypes:

```bash
nextflow \
  -c nextflow.config \
  -c runner/talos_fastspliceai.config \
  run main.nf \
  --input_tsv /path/to/talos_input.tsv \
  --processed_annotations processed_annotations \
  --spliceai_mode fastspliceai_cache \
  --fastspliceai_bin /path/to/fastspliceai_pip/bin/spliceai \
  --fastspliceai_reference large_files/ref.fa \
  --fastspliceai_cache /shared/fastspliceai_cache.vcf.gz \
  -output-dir /path/to/talos_outputs
```

Keep separate cache paths for each FastSpliceAI release, model configuration,
and reference build. Full parameter details are in
[`docs/NextflowConfiguration.md`](docs/NextflowConfiguration.md).

In `fastspliceai_cache` mode, cache inspection runs as a local CPU process
first. A fully cached rerun does not submit a GPU job. If new normalized
alleles are found, only those alleles are submitted to the GPU process; the
successful results are merged into the shared cache under a file lock.

### Web Runner

The optional Reflex runner is a web interface only: it submits the same
standalone preflight, preparation, and TALOS scripts that can be run from a
terminal. Its project defaults, shared resources, runtime paths, and GPU
settings are configured in [`runner/runner.config`](runner/runner.config).

```bash
REFLEX_CONDA_ENV=/faststorage/project/reanalyses_auh/env/talos2_env \
  bash runner/run_reflex_excel_runner.sh
```

See [`runner/README.md`](runner/README.md) for runner usage and configuration.

### Standalone Preflight

The AUH preflight workflow is kept separate from Talos proper under [`preflight/`](preflight/).

It covers:

- direct manifest input
- optional Excel-to-manifest mapping
- single-sample VCF preparation
- optional common-dbSNP subtraction
- family merge
- cohort merge
- optional SpliceAI annotation

Generic manifest-mode example:

```bash
nextflow run preflight/main.nf \
  -c preflight/nextflow.config \
  -c preflight/local.config \
  --sample_manifest preflight/examples/first_trio/sample_manifest.tsv \
  --pedigree preflight/examples/first_trio/pedigree.ped \
  -output-dir preflight/results
```

Synthetic preflight smoke test:

```bash
bash preflight/example_preflight.sh
```

Synthetic preflight plus Talos Apptainer smoke test:

```bash
bash preflight/example_with_talos_apptainer.sh
```

### Two-Family Direct Example

The simplest direct layout for many samples is:

- one `sample_manifest.tsv` with one row per single-sample VCF
- one `pedigree.ped` with all families
- one preflight run producing a merged cohort VCF
- one Talos TSV row pointing at that merged cohort VCF

Example `sample_manifest.tsv` for two trios:

```tsv
sample_id	vcf_path
PROBAND_A	/data/vcfs/PROBAND_A.vcf.gz
FATHER_A	/data/vcfs/FATHER_A.vcf.gz
MOTHER_A	/data/vcfs/MOTHER_A.vcf.gz
PROBAND_B	/data/vcfs/PROBAND_B.vcf.gz
FATHER_B	/data/vcfs/FATHER_B.vcf.gz
MOTHER_B	/data/vcfs/MOTHER_B.vcf.gz
```

Example `pedigree.ped`:

```tsv
FAM_A	PROBAND_A	FATHER_A	MOTHER_A	1	2
FAM_A	FATHER_A	0	0	1	1
FAM_A	MOTHER_A	0	0	2	1
FAM_B	PROBAND_B	FATHER_B	MOTHER_B	2	2
FAM_B	FATHER_B	0	0	1	1
FAM_B	MOTHER_B	0	0	2	1
```

Native preflight:

```bash
export PATH=/path/to/talos2_env/bin:$PATH
nextflow run preflight/main.nf \
  -c preflight/nextflow.config \
  -c preflight/local.config \
  --sample_manifest /path/to/sample_manifest.tsv \
  --pedigree /path/to/pedigree.ped \
  -output-dir /path/to/preflight_results
```

Native Talos:

```bash
nextflow -c nextflow.config run main.nf \
  --input_tsv /path/to/talos_input.tsv \
  --processed_annotations /path/to/processed_annotations \
  -output-dir /path/to/talos_outputs
```

Apptainer preflight:

```bash
apptainer exec \
  --bind /path/to/repo:/path/to/repo \
  --bind /path/to/data:/path/to/data \
  --pwd /path/to/repo \
  /path/to/talos-nextflow.sif \
  nextflow run preflight/main.nf \
    -c preflight/nextflow.config \
    -c preflight/local.config \
    --sample_manifest /path/to/sample_manifest.tsv \
    --pedigree /path/to/pedigree.ped \
    -output-dir /path/to/preflight_results
```

Apptainer Talos:

```bash
apptainer exec \
  --bind /path/to/repo:/path/to/repo \
  --bind /path/to/data:/path/to/data \
  --pwd /path/to/repo \
  /path/to/talos-nextflow.sif \
  nextflow -c nextflow.config run main.nf \
    --input_tsv /path/to/talos_input.tsv \
    --processed_annotations /path/to/processed_annotations \
    -output-dir /path/to/talos_outputs
```

For this AUH checkout, a local ignored runner script can also be created and run
in-place for two real trios. It generates its own `sample_manifest.tsv`,
`pedigree.ped`, `preflight.local.config`, and `talos_input.tsv` in the folder
where the script lives.

Local ignored example runners live under `local_examples/`, for example:

```bash
bash local_examples/run_single_trio_example.sh apptainer
bash local_examples/run_two_trios_example.sh native
```

### Family Bundle Generator

For real inputs, generate a timestamped ignored bundle with generic family roles:

```bash
bash preflight/create_family_bundle.sh \
  --proband /path/to/PROBAND.vcf.gz \
  --mother /path/to/MOTHER.vcf.gz \
  --father /path/to/FATHER.vcf.gz
```

Fast smoke mode keeps only the first variant from each provided VCF:

```bash
bash preflight/create_family_bundle.sh \
  --proband /path/to/PROBAND.vcf.gz \
  --mother /path/to/MOTHER.vcf.gz \
  --father /path/to/FATHER.vcf.gz \
  --fast true
```

This creates a local ignored bundle under `trio_runs/` with:

- `sample_manifest.tsv`
- `pedigree.ped`
- `preflight.local.config`
- `run_full_slurm.sh`

The generated script can be run either directly or through Slurm:

```bash
bash trio_runs/<bundle_name>/run_full_slurm.sh
```

```bash
sbatch trio_runs/<bundle_name>/run_full_slurm.sh
```

### Apptainer Build

The Apptainer tooling lives in [`apptainer/`](apptainer/).

Typical flow:

```bash
bash apptainer/fetch_env_to_folder.sh
bash apptainer/build_sif.sh
```

See [apptainer/README.md](apptainer/README.md) for details.

### Output Summary

Talos produces:

- JSON results for each cohort
- optional HTML reports
- labelled VCF outputs
- PanelApp cohort JSON
- reanalysis metadata such as `first_seen` and `evidence_last_updated`

The preflight layer produces:

- `prepared_manifest.tsv`
- family merge plan
- cohort merged VCF
- optional `cohort_merged_spliceai.vcf.gz`

## Part 2. Original Talos Basis

This repository is based on **Talos**, developed by the Population Genomics team.
The AUH extension keeps the core Talos method and overall workflow structure while
modifying runtime packaging, preflight handling, and local deployment patterns.

Upstream Talos overview:

- scalable variant prioritisation in known disease genes
- ACMG/AMP-aligned rule-based logic modules
- ClinVar and PanelApp-driven reanalysis support
- cohort-scale reruns with prior-history tracking

Primary upstream workflows:

- `preparation.nf`
- `main.nf`
- `talos_only.nf`

Primary upstream documentation:

- <https://populationgenomics.github.io/talos/>
- [docs/getting-started.md](docs/getting-started.md)
- [docs/Configuration.md](docs/Configuration.md)
- [docs/NextflowConfiguration.md](docs/NextflowConfiguration.md)

### Acknowledgement

This AUH fork builds on the original Talos project and its workflow design,
documentation base, and variant prioritisation framework.

If you use Talos in research or clinical work, cite the original publication:

Welland MJ, Ahlquist KD, De Fazio P, et al. Scalable automated reanalysis of
genomic data in research and clinical rare disease cohorts. *Nature Medicine*
(2026). <https://doi.org/10.1038/s41591-026-04477-5>
