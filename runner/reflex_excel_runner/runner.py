import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterator

from .paths import PREFLIGHT_RUN_SCRIPT, TALOS_RUN_SCRIPT, WORKSPACE_DIR


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def format_command_multiline(command: list[str]) -> str:
    if not command:
        return ""
    first_option = next((idx for idx, part in enumerate(command) if part.startswith("-")), len(command))
    lines = [" ".join(shlex.quote(part) for part in command[:first_option])]
    idx = first_option
    while idx < len(command):
        part = command[idx]
        if part.startswith("-") and idx + 1 < len(command) and not command[idx + 1].startswith("-"):
            rendered = f"{shlex.quote(part)} {shlex.quote(command[idx + 1])}"
            idx += 2
        else:
            rendered = shlex.quote(part)
            idx += 1
        lines[-1] += " \\"
        lines.append(f"  {rendered}")
    return "\n".join(lines)


def stream_process(command: list[str], cwd: Path) -> Iterator[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        yield line

    return_code = process.wait()
    yield f"\nProcess exited with code {return_code}\n"
    if return_code != 0:
        raise RuntimeError(f"Process exited with code {return_code}")


def run_bash_script(script: Path) -> Iterator[str]:
    yield from stream_process(["bash", str(script)], script.parent)


def build_preparation_command(
    processed_annotations: str,
    large_files: str,
    env_prefix: str = "",
) -> list[str]:
    processed_annotations = processed_annotations.strip() or "processed_annotations"
    large_files = large_files.strip() or "large_files"
    env_prefix = env_prefix.strip()
    nextflow = str(Path(env_prefix).expanduser() / "bin" / "nextflow") if env_prefix else "nextflow"
    command = [
        nextflow,
        "-c",
        "nextflow.config",
        "run",
        "preparation.nf",
        "--processed_annotations",
        processed_annotations,
        "--large_files",
        large_files,
    ]
    return command


def run_preparation(
    work_dir: Path,
    processed_annotations: str,
    large_files: str,
    env_prefix: str = "",
) -> Iterator[str]:
    yield from stream_process(
        build_preparation_command(processed_annotations, large_files, env_prefix),
        work_dir,
    )


def normalise_source_vcf_folders(source_vcf_folder: str) -> str:
    return "|".join(part.strip() for part in source_vcf_folder.replace("\n", "|").split("|") if part.strip())


def build_preflight_prepare_command(
    project_dir: str,
    samplelist: str,
    source_vcf_folder: str,
    department: str = "DEPT",
    inputs_dir: str = "inputs",
    symlink_dir: str = "VCF_symlinks",
) -> list[str]:
    project = Path(project_dir).expanduser()
    command = ["python3", "prepare_dept_preflight_inputs.py", "--samplelist", samplelist.strip()]
    department = department.strip()
    if department:
        command.extend(["--department", department])
    source_roots = normalise_source_vcf_folders(source_vcf_folder)
    if source_roots:
        command.extend(["--mapping-roots", source_roots])
    command.extend(
        [
            "--manifest-output",
            str(project / inputs_dir / "sample_manifest.tsv"),
            "--pedigree-output",
            str(project / inputs_dir / "pedigree.ped"),
            "--report-output",
            str(project / inputs_dir / "mapping_report.tsv"),
            "--symlink-dir",
            str(project / symlink_dir),
        ],
    )
    return command


def build_preflight_run_command(
    project_dir: str,
    resume: bool,
    inputs_dir: str = "inputs",
    outputs_dir: str = "outputs",
    work_dir: str = "work",
    nextflow_log: str = ".nextflow.log",
    talos_cohort: str = "DEPT",
    talos_config: str = "config/config.toml",
    spliceai_enabled: bool = False,
    spliceai_vcf: str = "",
    family_merge_enabled: bool = False,
) -> list[str]:
    project = Path(project_dir).expanduser()
    command = [
        "bash",
        str(PREFLIGHT_RUN_SCRIPT),
        "--run-dir",
        str(project),
        "--sample-manifest",
        str(project / inputs_dir / "sample_manifest.tsv"),
        "--pedigree",
        str(project / inputs_dir / "pedigree.ped"),
        "--output-dir",
        str(project / outputs_dir),
        "--work-dir",
        str(project / work_dir),
        "--log-file",
        str(project / nextflow_log),
        "--talos-cohort",
        talos_cohort.strip() or "DEPT",
        "--talos-config",
        str(project_path(project_dir, talos_config)),
        "--spliceai-enabled",
        "true" if spliceai_enabled else "false",
        "--family-merge-enabled",
        "true" if family_merge_enabled else "false",
    ]
    if spliceai_enabled and spliceai_vcf.strip():
        command.extend(["--spliceai-vcf", str(project_path(project_dir, spliceai_vcf))])
    command.extend(["--resume", "true" if resume else "false"])
    return command


def preflight_log_dir(project_dir: str, log_dir: str = "logs") -> Path:
    return Path(project_dir).expanduser() / log_dir


def project_path(project_dir: str, value: str) -> Path:
    path = Path(value.strip()).expanduser()
    if path.is_absolute():
        return path
    return Path(project_dir).expanduser() / path


def write_preflight_sbatch_script(
    project_dir: str,
    samplelist: str,
    source_vcf_folder: str,
    resume: bool,
    department: str = "DEPT",
    inputs_dir: str = "inputs",
    symlink_dir: str = "VCF_symlinks",
    outputs_dir: str = "outputs",
    work_dir: str = "work",
    log_dir_name: str = "logs",
    nextflow_log: str = ".nextflow.log",
    job_name: str = "talos_preflight",
    talos_cohort: str = "DEPT",
    talos_config: str = "config/config.toml",
    spliceai_enabled: bool = False,
    spliceai_vcf: str = "",
    cpus: str = "6",
    mem: str = "64G",
    time_limit: str = "24:00:00",
    family_merge_enabled: bool = False,
) -> Path:
    project = Path(project_dir).expanduser()
    log_dir = preflight_log_dir(project_dir, log_dir_name)
    log_dir.mkdir(parents=True, exist_ok=True)
    script_path = log_dir / f"{job_name}.sbatch"
    stdout_pattern = log_dir / f"{job_name}_%j.out"
    stderr_pattern = log_dir / f"{job_name}_%j.err"
    run_command = format_command_multiline(
        build_preflight_run_command(
            project_dir,
            resume,
            inputs_dir,
            outputs_dir,
            work_dir,
            nextflow_log,
            talos_cohort,
            talos_config,
            spliceai_enabled,
            spliceai_vcf,
            family_merge_enabled,
        ),
    )
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"#SBATCH --job-name={job_name}",
                f"#SBATCH --output={stdout_pattern}",
                f"#SBATCH --error={stderr_pattern}",
                f"#SBATCH --cpus-per-task={cpus}",
                f"#SBATCH --mem={mem}",
                f"#SBATCH --time={time_limit}",
                "",
                "set -euo pipefail",
                f"cd {shlex.quote(str(WORKSPACE_DIR))}",
                format_command_multiline(build_preflight_prepare_command(project_dir, samplelist, source_vcf_folder, department, inputs_dir, symlink_dir)),
                run_command,
                "",
            ],
        ),
    )
    return script_path


def submit_preflight_sbatch(
    project_dir: str,
    samplelist: str,
    source_vcf_folder: str,
    resume: bool,
    department: str = "DEPT",
    inputs_dir: str = "inputs",
    symlink_dir: str = "VCF_symlinks",
    outputs_dir: str = "outputs",
    work_dir: str = "work",
    log_dir: str = "logs",
    nextflow_log: str = ".nextflow.log",
    job_name: str = "talos_preflight",
    talos_cohort: str = "DEPT",
    talos_config: str = "config/config.toml",
    spliceai_enabled: bool = False,
    spliceai_vcf: str = "",
    cpus: str = "6",
    mem: str = "64G",
    time_limit: str = "24:00:00",
    family_merge_enabled: bool = False,
) -> tuple[str, str, Path]:
    project = Path(project_dir).expanduser()
    script_path = write_preflight_sbatch_script(
        project_dir,
        samplelist,
        source_vcf_folder,
        resume,
        department,
        inputs_dir,
        symlink_dir,
        outputs_dir,
        work_dir,
        log_dir,
        nextflow_log,
        job_name,
        talos_cohort,
        talos_config,
        spliceai_enabled,
        spliceai_vcf,
        cpus,
        mem,
        time_limit,
        family_merge_enabled,
    )
    process = subprocess.run(
        ["sbatch", str(script_path)],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = process.stdout
    job_id = ""
    for token in output.strip().split():
        if token.isdigit():
            job_id = token
    return output, job_id, script_path


def write_talos_sbatch_script(
    project_dir: str,
    tool_dir: str,
    input_tsv: str,
    output_dir: str,
    processed_annotations: str,
    nextflow_config: str,
    conda_env: str,
    resume: bool,
    spliceai_mode: str = "precomputed",
    spliceai_vcf: str = "",
    fastspliceai_bin: str = "",
    fastspliceai_reference: str = "",
    fastspliceai_cache: str = "",
    fastspliceai_nextflow_config: str = "",
    fastspliceai_queue: str = "",
    fastspliceai_cluster_options: str = "",
    fastspliceai_cpus: str = "",
    fastspliceai_mem: str = "",
    fastspliceai_time: str = "",
    fastspliceai_annotation: str = "",
    log_dir_name: str = "logs",
    job_name: str = "talos_full",
    cpus: str = "6",
    mem: str = "64G",
    time_limit: str = "24:00:00",
) -> Path:
    project = Path(project_dir).expanduser()
    log_dir = project / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)
    script_path = log_dir / f"{job_name}.sbatch"
    stdout_pattern = log_dir / f"{job_name}_%j.out"
    stderr_pattern = log_dir / f"{job_name}_%j.err"
    command = build_talos_run_command(
        project_dir,
        tool_dir,
        input_tsv,
        output_dir,
        processed_annotations,
        nextflow_config,
        conda_env,
        resume,
        spliceai_mode,
        spliceai_vcf,
        fastspliceai_bin,
        fastspliceai_reference,
        fastspliceai_cache,
        fastspliceai_nextflow_config,
        fastspliceai_queue,
        fastspliceai_cluster_options,
        fastspliceai_cpus,
        fastspliceai_mem,
        fastspliceai_time,
        fastspliceai_annotation,
    )
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"#SBATCH --job-name={job_name}",
                f"#SBATCH --output={stdout_pattern}",
                f"#SBATCH --error={stderr_pattern}",
                f"#SBATCH --cpus-per-task={cpus}",
                f"#SBATCH --mem={mem}",
                f"#SBATCH --time={time_limit}",
                "",
                "set -euo pipefail",
                format_command_multiline(command),
                "",
            ],
        ),
    )
    return script_path


def build_talos_run_command(
    project_dir: str,
    tool_dir: str,
    input_tsv: str,
    output_dir: str,
    processed_annotations: str,
    nextflow_config: str,
    conda_env: str,
    resume: bool,
    spliceai_mode: str = "precomputed",
    spliceai_vcf: str = "",
    fastspliceai_bin: str = "",
    fastspliceai_reference: str = "",
    fastspliceai_cache: str = "",
    fastspliceai_nextflow_config: str = "",
    fastspliceai_queue: str = "",
    fastspliceai_cluster_options: str = "",
    fastspliceai_cpus: str = "",
    fastspliceai_mem: str = "",
    fastspliceai_time: str = "",
    fastspliceai_annotation: str = "",
) -> list[str]:
    command = [
        "bash",
        str(TALOS_RUN_SCRIPT),
        "--run-dir",
        str(Path(project_dir).expanduser()),
        "--repo-dir",
        str(Path(tool_dir).expanduser()),
        "--conda-env",
        conda_env,
        "--input-tsv",
        str(project_path(project_dir, input_tsv)),
        "--output-dir",
        str(project_path(project_dir, output_dir)),
        "--processed-annotations",
        str(project_path(project_dir, processed_annotations)),
        "--nextflow-config",
        str(project_path(project_dir, nextflow_config)),
        "--spliceai-mode",
        spliceai_mode,
    ]
    if spliceai_mode == "precomputed" and spliceai_vcf.strip():
        command.extend(["--spliceai-vcf", str(project_path(project_dir, spliceai_vcf))])
    if spliceai_mode in {"fastspliceai", "fastspliceai_cache"}:
        command.extend(
            [
                "--fastspliceai-bin", fastspliceai_bin,
                "--fastspliceai-reference", fastspliceai_reference,
                "--fastspliceai-annotation", fastspliceai_annotation,
                "--fastspliceai-cache", fastspliceai_cache,
                "--fastspliceai-nextflow-config", str(
                    Path(fastspliceai_nextflow_config).expanduser()
                    if Path(fastspliceai_nextflow_config).expanduser().is_absolute()
                    else Path(tool_dir).expanduser() / fastspliceai_nextflow_config
                ),
                "--fastspliceai-queue", fastspliceai_queue,
                "--fastspliceai-cluster-options", fastspliceai_cluster_options,
                "--fastspliceai-cpus", fastspliceai_cpus,
                "--fastspliceai-mem", fastspliceai_mem,
                "--fastspliceai-time", fastspliceai_time,
            ],
        )
    command.extend(["--resume", "true" if resume else "false"])
    return command


def submit_talos_sbatch(
    project_dir: str,
    tool_dir: str,
    input_tsv: str,
    output_dir: str,
    processed_annotations: str,
    nextflow_config: str,
    conda_env: str,
    resume: bool,
    spliceai_mode: str = "precomputed",
    spliceai_vcf: str = "",
    fastspliceai_bin: str = "",
    fastspliceai_reference: str = "",
    fastspliceai_cache: str = "",
    fastspliceai_nextflow_config: str = "",
    fastspliceai_queue: str = "",
    fastspliceai_cluster_options: str = "",
    fastspliceai_cpus: str = "",
    fastspliceai_mem: str = "",
    fastspliceai_time: str = "",
    fastspliceai_annotation: str = "",
    log_dir: str = "logs",
    job_name: str = "talos_full",
    cpus: str = "6",
    mem: str = "64G",
    time_limit: str = "24:00:00",
) -> tuple[str, str, Path]:
    project = Path(project_dir).expanduser()
    script_path = write_talos_sbatch_script(
        project_dir,
        tool_dir,
        input_tsv,
        output_dir,
        processed_annotations,
        nextflow_config,
        conda_env,
        resume,
        spliceai_mode,
        spliceai_vcf,
        fastspliceai_bin,
        fastspliceai_reference,
        fastspliceai_cache,
        fastspliceai_nextflow_config,
        fastspliceai_queue,
        fastspliceai_cluster_options,
        fastspliceai_cpus,
        fastspliceai_mem,
        fastspliceai_time,
        fastspliceai_annotation,
        log_dir,
        job_name,
        cpus,
        mem,
        time_limit,
    )
    process = subprocess.run(
        ["sbatch", str(script_path)],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = process.stdout
    job_id = ""
    for token in output.strip().split():
        if token.isdigit():
            job_id = token
    return output, job_id, script_path


def slurm_job_state(job_id: str) -> str:
    if not job_id:
        return ""
    try:
        process = subprocess.run(
            ["squeue", "--noheader", "--jobs", job_id, "--format", "%T"],
            cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return ""
    return process.stdout.strip().splitlines()[0].strip() if process.stdout.strip() else ""


def active_slurm_job(job_name: str) -> tuple[str, str]:
    command = ["squeue", "--noheader", "--name", job_name, "--format", "%A\t%T"]
    user = os.environ.get("USER")
    if user:
        command[1:1] = ["--user", user]
    try:
        process = subprocess.run(
            command,
            cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return "", ""
    for line in process.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    return "", ""


def cancel_slurm_job(job_id: str) -> str:
    try:
        process = subprocess.run(
            ["scancel", job_id],
            cwd=WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return f"Timed out while cancelling Slurm job {job_id}\n"
    return process.stdout


def read_preflight_logs(
    project_dir: str,
    job_id: str,
    log_dir_name: str = "logs",
    nextflow_log_name: str = ".nextflow.log",
    job_name: str = "talos_preflight",
) -> tuple[str, str, str]:
    screen_output = ""
    stderr_output = ""
    log_dir = preflight_log_dir(project_dir, log_dir_name)
    if job_id:
        stdout_path = log_dir / f"{job_name}_{job_id}.out"
        if stdout_path.exists():
            screen_output = stdout_path.read_text(errors="replace")
        else:
            screen_output = f"Not written yet: {stdout_path}\n"

        stderr_path = log_dir / f"{job_name}_{job_id}.err"
        if stderr_path.exists():
            stderr_output = stderr_path.read_text(errors="replace")
        else:
            stderr_output = f"Not written yet: {stderr_path}\n"
    else:
        screen_output = "No Slurm job id yet.\n"
        stderr_output = "No Slurm job id yet.\n"

    nextflow_log = Path(project_dir).expanduser() / nextflow_log_name
    if nextflow_log.exists():
        content = nextflow_log.read_text(errors="replace")
        nextflow_tail = "\n".join(content.splitlines()[-240:]) + "\n"
    else:
        nextflow_tail = f"Not written yet: {nextflow_log}\n"

    return screen_output, stderr_output, nextflow_tail


def read_nextflow_log_tail(project_dir: str, nextflow_log_name: str = ".nextflow.log") -> str:
    nextflow_log = Path(project_dir).expanduser() / nextflow_log_name
    if not nextflow_log.exists():
        return f"Not written yet: {nextflow_log}\n"

    content = nextflow_log.read_text(errors="replace")
    return "\n".join(content.splitlines()[-1000:]) + "\n"


def read_slurm_logs(
    project_dir: str,
    job_id: str,
    log_dir_name: str = "logs",
    job_name: str = "talos_full",
) -> tuple[str, str, str]:
    log_dir = Path(project_dir).expanduser() / log_dir_name
    if not job_id:
        return "No Slurm job id yet.\n", "No Slurm job id yet.\n", read_nextflow_log_tail(project_dir)

    stdout_path = log_dir / f"{job_name}_{job_id}.out"
    stderr_path = log_dir / f"{job_name}_{job_id}.err"
    screen_output = (
        stdout_path.read_text(errors="replace")
        if stdout_path.exists()
        else f"Not written yet: {stdout_path}\n"
    )
    stderr_output = (
        stderr_path.read_text(errors="replace")
        if stderr_path.exists()
        else f"Not written yet: {stderr_path}\n"
    )
    return screen_output, stderr_output, read_nextflow_log_tail(project_dir)
