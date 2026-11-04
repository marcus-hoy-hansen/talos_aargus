import asyncio
from pathlib import Path

import reflex as rx

from . import config_io, runner
from .excel_io import (
    SAMPLE_FILE,
    ensure_sample_excel,
    parse_tsv,
    read_excel_preview,
    rows_to_tsv,
    write_xlsx_rows,
)
from .paths import (
    DEFAULT_PREFLIGHT_PROJECT_DIR,
    DEFAULT_PREFLIGHT_SAMPLELIST_FILENAME,
    PREPARATION_LARGE_FILES,
    PREPARATION_PROCESSED_ANNOTATIONS,
    PREFLIGHT_RUN_SCRIPT,
    RUNNER_CONFIG_FILE,
    RESOURCE_SCRIPT_CANDIDATES,
    TALOS_RUN_SCRIPT,
    TALOS_REPO_DIR,
    ensure_dirs,
)


class AppState(rx.State):
    active_tab: str = "import"
    status: str = "Ready"

    uploaded_file: str = ""
    preview_columns: list[str] = []
    preview_rows: list[list[str]] = []
    excel_editor_text: str = ""
    excel_output_path: str = ""
    excel_delete_row: str = ""

    config_text: str = ""
    config_path: str = str(RUNNER_CONFIG_FILE)
    config_dialog_open: bool = False
    config_candidate: str = str(RUNNER_CONFIG_FILE)
    config_candidates: list[str] = [str(RUNNER_CONFIG_FILE)]

    resource_script_path: str = ""
    resource_script_candidates: list[str] = []
    resource_command_preview: str = ""
    resource_output: str = ""
    resource_status: str = "Idle"

    preparation_work_dir: str = str(TALOS_REPO_DIR)
    preparation_processed_annotations: str = PREPARATION_PROCESSED_ANNOTATIONS
    preparation_large_files: str = PREPARATION_LARGE_FILES
    preparation_env_prefix: str = "/faststorage/project/reanalyses_auh/env/talos2_env"
    preparation_command_preview: str = ""
    preparation_output: str = ""
    preparation_status: str = "Idle"

    preflight_project_dir: str = str(DEFAULT_PREFLIGHT_PROJECT_DIR)
    preflight_project_dialog_open: bool = False
    preflight_project_candidate: str = str(DEFAULT_PREFLIGHT_PROJECT_DIR)
    preflight_samplelist_filename: str = DEFAULT_PREFLIGHT_SAMPLELIST_FILENAME
    preflight_samplelist: str = str(DEFAULT_PREFLIGHT_PROJECT_DIR / DEFAULT_PREFLIGHT_SAMPLELIST_FILENAME)
    preflight_project_choices: list[str] = []
    preflight_source_vcf_folder: str = ""
    preflight_department: str = "DEPT"
    preflight_inputs_dir: str = "inputs"
    preflight_outputs_dir: str = "outputs"
    preflight_work_dir: str = "work"
    preflight_log_dir: str = "logs"
    preflight_nextflow_log_name: str = ".nextflow.log"
    preflight_symlink_dir: str = "VCF_symlinks"
    preflight_job_name: str = "talos_preflight"
    preflight_talos_cohort: str = "DEPT"
    preflight_talos_config: str = "config/config.toml"
    preflight_spliceai_enabled: bool = False
    preflight_spliceai_vcf: str = "/faststorage/project/reanalyses_auh/resources/spliceai_scores_KGA_AUH_GRCh_38_Homo_sapiens_converted.vcf.gz"
    preflight_family_merge_enabled: bool = False
    preflight_cpus: str = "6"
    preflight_mem: str = "64G"
    preflight_time: str = "24:00:00"
    preflight_resume: bool = True
    preflight_command_preview: str = ""
    preflight_output: str = ""
    preflight_stderr_output: str = ""
    preflight_nextflow_log: str = ""
    preflight_log_revision: int = 0
    preflight_status: str = "Idle"
    preflight_job_id: str = ""
    preflight_sbatch_script: str = ""
    preflight_running: bool = False

    talos_project_dir: str = str(DEFAULT_PREFLIGHT_PROJECT_DIR)
    talos_tool_dir: str = str(TALOS_REPO_DIR)
    talos_input_tsv: str = "outputs/talos_input.tsv"
    talos_output_dir: str = "cohort_outputs"
    talos_processed_annotations: str = str(TALOS_REPO_DIR / "processed_annotations")
    talos_nextflow_config: str = "config/dept_local.config"
    talos_conda_env: str = "talos2_env"
    talos_spliceai_mode: str = "precomputed"
    talos_spliceai_vcf: str = "/faststorage/project/reanalyses_auh/resources/spliceai_scores_KGA_AUH_GRCh_38_Homo_sapiens_converted.vcf.gz"
    talos_fastspliceai_bin: str = "/faststorage/project/reanalyses_auh/env/fastspliceai_pip/bin/spliceai"
    talos_fastspliceai_reference: str = str(TALOS_REPO_DIR / "large_files" / "ref.fa")
    talos_fastspliceai_annotation: str = str(TALOS_REPO_DIR / "resources" / "grch38_MANE_v1.5.txt")
    talos_fastspliceai_cache: str = "/faststorage/project/reanalyses_auh/v2/spliceai_cache/cache_mane_v1.5.vcf.gz"
    talos_fastspliceai_nextflow_config: str = str(TALOS_REPO_DIR / "runner" / "talos_fastspliceai.config")
    talos_fastspliceai_queue: str = "gpu-l40s,gpu-h200"
    talos_fastspliceai_cluster_options: str = "--account=reanalyses_auh --gpus=1"
    talos_fastspliceai_cpus: str = "6"
    talos_fastspliceai_mem: str = "16G"
    talos_fastspliceai_time: str = "08:00:00"
    talos_log_dir: str = "logs"
    talos_job_name: str = "talos_full"
    talos_cpus: str = "6"
    talos_mem: str = "64G"
    talos_time: str = "24:00:00"
    talos_resume: bool = True
    talos_command_preview: str = ""
    talos_output: str = ""
    talos_stderr_output: str = ""
    talos_nextflow_log: str = ""
    talos_log_revision: int = 0
    talos_status: str = "Idle"
    talos_job_id: str = ""
    talos_sbatch_script: str = ""
    talos_running: bool = False
    settings_loaded: bool = False
    log_autorefresh_running: bool = False

    @rx.var
    def has_preview(self) -> bool:
        return bool(self.preview_columns)

    def set_tab(self, tab: str):
        self.active_tab = tab

    def on_load(self):
        ensure_dirs()
        ensure_sample_excel()
        if not self.settings_loaded:
            self.load_rows_from_path(SAMPLE_FILE)
            self.reload_config()
            self.refresh_preflight_projects()
            self.settings_loaded = True
        self.refresh_preflight_state()
        self.refresh_talos_state()
        return AppState.autorefresh_logs

    @rx.event(background=True)
    async def autorefresh_logs(self):
        async with self:
            if self.log_autorefresh_running:
                return
            self.log_autorefresh_running = True

        while True:
            await asyncio.sleep(30)
            async with self:
                if self.preflight_running:
                    self._refresh_preflight_log(update_status=False)
                if self.talos_running:
                    self._refresh_talos_log(update_status=False)
                if not self.preflight_running and not self.talos_running:
                    self.log_autorefresh_running = False
                    return
            yield

    def load_runner_settings(self):
        config = config_io.load_runner_config(self.config_path)
        project_dir = config.get("PREFLIGHT_DEFAULT_PROJECT_DIR")
        if project_dir:
            self.preflight_project_dir = project_dir
        self.preflight_project_candidate = self.preflight_project_dir
        self.preflight_samplelist_filename = config.get(
            "PREFLIGHT_SAMPLELIST_FILENAME",
            self.preflight_samplelist_filename,
        )
        self.preflight_samplelist = str(Path(self.preflight_project_dir) / self.preflight_samplelist_filename)
        folders = config.get("PREFLIGHT_SOURCE_VCF_FOLDERS", "")
        self.preflight_source_vcf_folder = folders.replace("|", "\n")
        self.preflight_department = config.get("PREFLIGHT_DEPARTMENT", self.preflight_department)
        self.preflight_inputs_dir = config.get("PREFLIGHT_INPUTS_DIR", self.preflight_inputs_dir)
        self.preflight_outputs_dir = config.get("PREFLIGHT_OUTPUTS_DIR", self.preflight_outputs_dir)
        self.preflight_work_dir = config.get("PREFLIGHT_WORK_DIR", self.preflight_work_dir)
        self.preflight_log_dir = config.get("PREFLIGHT_LOG_DIR", self.preflight_log_dir)
        self.preflight_nextflow_log_name = config.get("PREFLIGHT_NEXTFLOW_LOG", self.preflight_nextflow_log_name)
        self.preflight_symlink_dir = config.get("PREFLIGHT_SYMLINK_DIR", self.preflight_symlink_dir)
        self.preflight_job_name = config.get("PREFLIGHT_JOB_NAME", self.preflight_job_name)
        self.preflight_talos_cohort = config.get("PREFLIGHT_TALOS_COHORT", self.preflight_talos_cohort)
        self.preflight_talos_config = config.get("PREFLIGHT_TALOS_CONFIG", self.preflight_talos_config)
        self.preflight_spliceai_enabled = config.get(
            "PREFLIGHT_SPLICEAI_ENABLED",
            str(self.preflight_spliceai_enabled),
        ).lower() == "true"
        self.preflight_spliceai_vcf = config.get("PREFLIGHT_SPLICEAI_VCF", self.preflight_spliceai_vcf)
        self.preflight_family_merge_enabled = config.get(
            "PREFLIGHT_FAMILY_MERGE_ENABLED",
            str(self.preflight_family_merge_enabled),
        ).lower() == "true"
        self.preflight_cpus = config.get("PREFLIGHT_CPUS", self.preflight_cpus)
        self.preflight_mem = config.get("PREFLIGHT_MEM", self.preflight_mem)
        self.preflight_time = config.get("PREFLIGHT_TIME", self.preflight_time)
        self.preflight_resume = config.get("PREFLIGHT_RESUME", str(self.preflight_resume)).lower() == "true"

        self.preparation_work_dir = config.get("PREPARATION_WORK_DIR", self.preparation_work_dir)
        self.preparation_processed_annotations = config.get(
            "PREPARATION_PROCESSED_ANNOTATIONS",
            self.preparation_processed_annotations,
        )
        self.preparation_large_files = config.get("PREPARATION_LARGE_FILES", self.preparation_large_files)
        self.preparation_env_prefix = config.get("PREPARATION_ENV_PREFIX", self.preparation_env_prefix)

        resource_candidates = config.get("RESOURCE_SCRIPT_CANDIDATES", "")
        self.resource_script_candidates = [path for path in resource_candidates.split("|") if path]

        self.talos_tool_dir = config.get("TALOS_TOOL_DIR", self.talos_tool_dir)
        self.talos_project_dir = self.preflight_project_dir
        self.talos_input_tsv = config.get("TALOS_INPUT_TSV", self.talos_input_tsv)
        self.talos_output_dir = config.get("TALOS_OUTPUT_DIR", self.talos_output_dir)
        self.talos_processed_annotations = config.get(
            "TALOS_PROCESSED_ANNOTATIONS",
            self.talos_processed_annotations,
        )
        self.talos_nextflow_config = config.get("TALOS_NEXTFLOW_CONFIG", self.talos_nextflow_config)
        self.talos_conda_env = config.get("TALOS_CONDA_ENV", self.talos_conda_env)
        self.talos_spliceai_mode = config.get("TALOS_SPLICEAI_MODE", self.talos_spliceai_mode)
        self.talos_spliceai_vcf = config.get("TALOS_SPLICEAI_VCF", self.talos_spliceai_vcf)
        self.talos_fastspliceai_bin = config.get("TALOS_FASTSPLICEAI_BIN", self.talos_fastspliceai_bin)
        self.talos_fastspliceai_reference = config.get("TALOS_FASTSPLICEAI_REFERENCE", self.talos_fastspliceai_reference)
        self.talos_fastspliceai_annotation = config.get("TALOS_FASTSPLICEAI_ANNOTATION", self.talos_fastspliceai_annotation)
        self.talos_fastspliceai_cache = config.get("TALOS_FASTSPLICEAI_CACHE", self.talos_fastspliceai_cache)
        self.talos_fastspliceai_nextflow_config = config.get(
            "TALOS_FASTSPLICEAI_NEXTFLOW_CONFIG", self.talos_fastspliceai_nextflow_config,
        )
        self.talos_fastspliceai_queue = config.get("TALOS_FASTSPLICEAI_QUEUE", self.talos_fastspliceai_queue)
        self.talos_fastspliceai_cluster_options = config.get(
            "TALOS_FASTSPLICEAI_CLUSTER_OPTIONS", self.talos_fastspliceai_cluster_options,
        )
        self.talos_fastspliceai_cpus = config.get("TALOS_FASTSPLICEAI_CPUS", self.talos_fastspliceai_cpus)
        self.talos_fastspliceai_mem = config.get("TALOS_FASTSPLICEAI_MEM", self.talos_fastspliceai_mem)
        self.talos_fastspliceai_time = config.get("TALOS_FASTSPLICEAI_TIME", self.talos_fastspliceai_time)
        self.talos_log_dir = config.get("TALOS_LOG_DIR", self.talos_log_dir)
        self.talos_job_name = config.get("TALOS_JOB_NAME", self.talos_job_name)
        self.talos_cpus = config.get("TALOS_CPUS", self.talos_cpus)
        self.talos_mem = config.get("TALOS_MEM", self.talos_mem)
        self.talos_time = config.get("TALOS_TIME", self.talos_time)
        self.talos_resume = config.get("TALOS_RESUME", str(self.talos_resume)).lower() == "true"

    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            self.status = "No file was selected."
            return

        ensure_dirs()
        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)

        file = files[0]
        target = upload_dir / file.name
        target.write_bytes(await file.read())
        self.load_rows_from_path(target)

    def load_sample(self):
        ensure_sample_excel()
        self.load_rows_from_path(SAMPLE_FILE)

    def load_rows_from_path(self, path: Path):
        columns, rows = read_excel_preview(path)
        self.uploaded_file = str(path)
        self.preview_columns = columns
        self.preview_rows = rows
        self.excel_editor_text = rows_to_tsv(columns, rows) if columns else ""
        self.excel_output_path = str(path.with_name(f"{path.stem}.edited.xlsx"))

        if columns:
            self.status = f"Loaded {len(rows)} rows from {path.name}"
        else:
            self.status = f"No rows found in {path.name}"

    def set_excel_editor_text(self, value: str):
        self.excel_editor_text = value
        self.update_excel_preview()

    def set_excel_output_path(self, value: str):
        self.excel_output_path = value

    def set_excel_delete_row(self, value: str):
        self.excel_delete_row = value

    def update_excel_preview(self):
        columns, rows = parse_tsv(self.excel_editor_text)
        self.preview_columns = columns
        self.preview_rows = rows
        self.status = f"Editor contains {len(rows)} rows"

    def add_excel_row(self):
        columns, rows = parse_tsv(self.excel_editor_text)
        if not columns:
            columns = ["sample", "family", "status"]
        rows.append([""] * len(columns))
        self.preview_columns = columns
        self.preview_rows = rows
        self.excel_editor_text = rows_to_tsv(columns, rows)
        self.status = "Added blank row"

    def delete_excel_row_by_index(self):
        columns, rows = parse_tsv(self.excel_editor_text)
        try:
            row_number = int(self.excel_delete_row)
        except ValueError:
            self.status = "Delete row must be a 1-based row number."
            return
        if row_number < 1 or row_number > len(rows):
            self.status = f"Delete row must be between 1 and {len(rows)}."
            return

        del rows[row_number - 1]
        self.preview_columns = columns
        self.preview_rows = rows
        self.excel_editor_text = rows_to_tsv(columns, rows)
        self.status = f"Deleted row {row_number}"

    def save_edited_excel(self):
        if not self.excel_output_path.strip():
            self.status = "Set an output Excel path before saving."
            return

        columns, rows = parse_tsv(self.excel_editor_text)
        if not columns:
            self.status = "No table header to save."
            return

        output_path = Path(self.excel_output_path).expanduser()
        try:
            write_xlsx_rows(output_path, columns, rows)
        except Exception as error:
            self.status = f"Save failed: {error}"
            return

        self.uploaded_file = str(output_path)
        self.preview_columns = columns
        self.preview_rows = rows
        self.status = f"Saved {len(rows)} rows to {output_path}"

    def load_config(self):
        self.config_text = config_io.read_runner_config_text(self.config_path)
        self.status = f"Loaded {self.config_path}"

    def refresh_config_candidates(self):
        candidates = [self.config_path, str(RUNNER_CONFIG_FILE)]
        candidates.extend(str(path) for path in RUNNER_CONFIG_FILE.parent.glob("*.config"))
        self.config_candidates = list(dict.fromkeys(candidates))

    def open_config_dialog(self):
        self.refresh_config_candidates()
        self.config_candidate = self.config_path
        self.config_dialog_open = True

    def close_config_dialog(self):
        self.config_dialog_open = False

    def set_config_dialog_open(self, value: bool):
        self.config_dialog_open = value

    def set_config_candidate(self, value: str):
        self.config_candidate = value

    def refresh_all_settings(self):
        self.load_runner_settings()
        self.resolve_resource_script()
        self.update_preparation_command_preview()
        self.refresh_preflight_projects()
        self.update_preflight_command_preview()
        self.update_talos_command_preview()

    def apply_config_candidate(self):
        path = config_io.config_path(self.config_candidate)
        if not path.is_file():
            self.status = f"Config file does not exist: {path}"
            return
        self.config_path = str(path)
        self.config_dialog_open = False
        try:
            self.load_config()
            self.refresh_all_settings()
            self.status = f"Loaded all settings from {path}"
        except ValueError as error:
            self.status = str(error)

    def set_config_text(self, value: str):
        self.config_text = value

    def save_config(self):
        config_io.write_runner_config_text(self.config_text, self.config_path)
        try:
            self.refresh_all_settings()
            self.status = f"Saved {self.config_path}"
        except ValueError as error:
            self.status = str(error)

    def reload_config(self):
        self.load_config()
        self.refresh_all_settings()

    def resolve_resource_script(self):
        candidates = [Path(path) for path in self.resource_script_candidates] or RESOURCE_SCRIPT_CANDIDATES
        for candidate in candidates:
            if candidate.exists():
                self.resource_script_path = str(candidate)
                self.resource_command_preview = runner.format_command(["bash", str(candidate)])
                return

        requested = candidates[0]
        self.resource_script_path = str(requested)
        self.resource_command_preview = f"Missing script: {requested}"

    def refresh_resource_script(self):
        self.resolve_resource_script()
        self.status = f"Resource script: {self.resource_script_path}"

    def run_resource_download(self):
        self.resolve_resource_script()
        script = Path(self.resource_script_path)
        if not script.exists():
            self.resource_status = "Missing"
            self.resource_output = f"Script does not exist: {script}\n"
            self.status = self.resource_status
            yield
            return

        command = ["bash", str(script)]
        self.resource_output = "$ " + runner.format_command(command) + "\n\n"
        self.resource_status = "Running"
        self.status = "Downloading resources"
        self.active_tab = "resources"
        yield

        try:
            for line in runner.run_bash_script(script):
                self.resource_output += line
                yield
            self.resource_status = "Finished"
            self.status = self.resource_status
            yield
        except Exception as error:
            self.resource_output += f"\nERROR: {error}\n"
            self.resource_status = "Failed"
            self.status = str(error)
            yield

    def set_preparation_processed_annotations(self, value: str):
        self.preparation_processed_annotations = value
        self.update_preparation_command_preview()

    def set_preparation_work_dir(self, value: str):
        self.preparation_work_dir = value
        self.update_preparation_command_preview()

    def set_preparation_large_files(self, value: str):
        self.preparation_large_files = value
        self.update_preparation_command_preview()

    def set_preparation_env_prefix(self, value: str):
        self.preparation_env_prefix = value
        self.update_preparation_command_preview()

    def update_preparation_command_preview(self):
        command = runner.build_preparation_command(
            self.preparation_processed_annotations,
            self.preparation_large_files,
            self.preparation_env_prefix,
        )
        self.preparation_command_preview = (
            f"cd {Path(self.preparation_work_dir)}\n"
            f"{runner.format_command_multiline(command)}"
        )

    def run_preparation(self):
        self.update_preparation_command_preview()
        work_dir = Path(self.preparation_work_dir)
        if not (work_dir / "nextflow.config").exists() or not (work_dir / "preparation.nf").exists():
            self.preparation_status = "Missing"
            self.preparation_output = f"Preparation workflow not found in: {work_dir}\n"
            self.status = self.preparation_status
            yield
            return

        self.preparation_output = "$ " + self.preparation_command_preview.replace("\n", "\n$ ") + "\n\n"
        self.preparation_status = "Running"
        self.status = "Running preparation"
        self.active_tab = "preparation"
        yield

        try:
            for line in runner.run_preparation(
                work_dir,
                self.preparation_processed_annotations,
                self.preparation_large_files,
                self.preparation_env_prefix,
            ):
                self.preparation_output += line
                yield
            self.preparation_status = "Finished"
            self.status = self.preparation_status
            yield
        except Exception as error:
            self.preparation_output += f"\nERROR: {error}\n"
            self.preparation_status = "Failed"
            self.status = str(error)
            yield

    def refresh_preflight_projects(self):
        root = Path(self.preflight_project_dir)
        choices = [str(root)]
        scan_root = root.parent if root.parent.is_dir() else DEFAULT_PREFLIGHT_PROJECT_DIR
        if not scan_root.is_dir():
            self.preflight_project_choices = choices
            return
        for child in sorted(scan_root.iterdir()):
            if child.is_dir() and (child / self.preflight_samplelist_filename).exists():
                choices.append(str(child))
        self.preflight_project_choices = list(dict.fromkeys(choices))

    def open_preflight_project_dialog(self):
        self.refresh_preflight_projects()
        self.preflight_project_candidate = self.preflight_project_dir
        self.preflight_project_dialog_open = True

    def close_preflight_project_dialog(self):
        self.preflight_project_dialog_open = False

    def set_preflight_project_dialog_open(self, value: bool):
        self.preflight_project_dialog_open = value

    def set_preflight_project_candidate(self, value: str):
        self.preflight_project_candidate = value

    def apply_preflight_project_candidate(self):
        self.set_preflight_project_dir(self.preflight_project_candidate)
        self.preflight_project_dialog_open = False

    def set_preflight_project_dir(self, value: str):
        self.preflight_project_dir = value
        project = Path(value.strip() or ".")
        self.preflight_samplelist = str(project / self.preflight_samplelist_filename)
        self.preflight_sbatch_script = str(project / self.preflight_log_dir / f"{self.preflight_job_name}.sbatch")
        self.talos_project_dir = value
        self.talos_sbatch_script = str(project / self.talos_log_dir / f"{self.talos_job_name}.sbatch")
        self.update_preflight_command_preview()
        self.update_talos_command_preview()

    def set_preflight_samplelist(self, value: str):
        self.preflight_samplelist = value
        self.update_preflight_command_preview()

    def set_preflight_source_vcf_folder(self, value: str):
        self.preflight_source_vcf_folder = value
        self.update_preflight_command_preview()

    def set_preflight_department(self, value: str):
        self.preflight_department = value
        self.update_preflight_command_preview()

    def clear_preflight_source_vcf_folder(self):
        self.preflight_source_vcf_folder = ""
        self.update_preflight_command_preview()

    def set_preflight_resume(self, value: bool):
        self.preflight_resume = value
        self.update_preflight_command_preview()

    def set_preflight_talos_cohort(self, value: str):
        self.preflight_talos_cohort = value
        self.update_preflight_command_preview()

    def set_preflight_talos_config(self, value: str):
        self.preflight_talos_config = value
        self.update_preflight_command_preview()

    def set_preflight_spliceai_enabled(self, value: bool):
        self.preflight_spliceai_enabled = value
        self.update_preflight_command_preview()

    def set_preflight_spliceai_vcf(self, value: str):
        self.preflight_spliceai_vcf = value
        self.update_preflight_command_preview()

    def update_preflight_command_preview(self):
        prepare_command = runner.format_command_multiline(
            runner.build_preflight_prepare_command(
                self.preflight_project_dir,
                self.preflight_samplelist,
                self.preflight_source_vcf_folder,
                self.preflight_department,
                self.preflight_inputs_dir,
                self.preflight_symlink_dir,
            ),
        )
        run_command = runner.format_command_multiline(
            runner.build_preflight_run_command(
                self.preflight_project_dir,
                self.preflight_resume,
                self.preflight_inputs_dir,
                self.preflight_outputs_dir,
                self.preflight_work_dir,
                self.preflight_nextflow_log_name,
                self.preflight_talos_cohort,
                self.preflight_talos_config,
                self.preflight_spliceai_enabled,
                self.preflight_spliceai_vcf,
                self.preflight_family_merge_enabled,
            ),
        )
        self.preflight_command_preview = f"{prepare_command}\n{run_command}"

    def refresh_preflight_state(self):
        state = runner.slurm_job_state(self.preflight_job_id)
        if state:
            self.preflight_running = True
            self.preflight_status = f"{state} {self.preflight_job_id}"
            return

        job_id, job_state = runner.active_slurm_job(self.preflight_job_name)
        if job_id:
            self.preflight_job_id = job_id
            self.preflight_running = True
            self.preflight_status = f"{job_state} {job_id}"
            return

        if self.preflight_running and self.preflight_job_id:
            self.preflight_status = f"Finished {self.preflight_job_id}"
        self.preflight_running = False

    def submit_preflight(self):
        self.refresh_preflight_state()
        if self.preflight_running:
            self.status = f"Preflight already active: {self.preflight_status}"
            yield
            return

        self.update_preflight_command_preview()
        project_dir = Path(self.preflight_project_dir)
        if not project_dir.exists() or not project_dir.is_dir():
            self.preflight_status = "Missing"
            self.preflight_output = f"Project folder does not exist: {project_dir}\n"
            self.status = self.preflight_status
            yield
            return
        samplelist = Path(self.preflight_samplelist)
        if not samplelist.exists():
            self.preflight_status = "Missing"
            self.preflight_output = f"Sample list does not exist: {samplelist}\n"
            self.status = self.preflight_status
            yield
            return
        if not PREFLIGHT_RUN_SCRIPT.exists():
            self.preflight_status = "Missing"
            self.preflight_output = f"Preflight wrapper does not exist: {PREFLIGHT_RUN_SCRIPT}\n"
            self.status = self.preflight_status
            yield
            return
        self.preflight_status = "Submitting"
        self.status = "Submitting preflight"
        self.active_tab = "preflight"
        self.preflight_output = "$ sbatch <project>/logs/talos_preflight.sbatch\n\n"
        self.preflight_stderr_output = ""
        self.preflight_nextflow_log = ""
        yield

        try:
            output, job_id, script_path = runner.submit_preflight_sbatch(
                self.preflight_project_dir,
                self.preflight_samplelist,
                self.preflight_source_vcf_folder,
                self.preflight_resume,
                self.preflight_department,
                self.preflight_inputs_dir,
                self.preflight_symlink_dir,
                self.preflight_outputs_dir,
                self.preflight_work_dir,
                self.preflight_log_dir,
                self.preflight_nextflow_log_name,
                self.preflight_job_name,
                self.preflight_talos_cohort,
                self.preflight_talos_config,
                self.preflight_spliceai_enabled,
                self.preflight_spliceai_vcf,
                self.preflight_cpus,
                self.preflight_mem,
                self.preflight_time,
                self.preflight_family_merge_enabled,
            )
            self.preflight_job_id = job_id
            self.preflight_sbatch_script = str(script_path)
            self.preflight_output += output
            self.preflight_output += f"\nsbatch script: {script_path}\n"
            if job_id:
                self.preflight_running = True
                self.preflight_status = f"Submitted {job_id}"
                self.status = self.preflight_status
            else:
                self.preflight_running = False
                self.preflight_status = "Submit failed"
                self.status = self.preflight_status
            yield
            self._refresh_preflight_log(update_status=False)
            yield AppState.autorefresh_logs
        except Exception as error:
            self.preflight_output += f"\nERROR: {error}\n"
            self.preflight_status = "Failed"
            self.preflight_running = False
            self.status = str(error)
            yield

    def cancel_preflight(self):
        self.refresh_preflight_state()
        if not self.preflight_running or not self.preflight_job_id:
            self.status = "No active preflight job to cancel"
            yield
            return

        job_id = self.preflight_job_id
        output = runner.cancel_slurm_job(job_id)
        if output:
            self.preflight_output += output
        self.preflight_running = False
        self.preflight_status = f"Cancel requested {job_id}"
        self.status = self.preflight_status
        yield
        self._refresh_preflight_log(update_status=False)
        yield

    def _refresh_preflight_log(self, update_status: bool):
        self.refresh_preflight_state()
        screen_output, stderr_output, nextflow_log = runner.read_preflight_logs(
            self.preflight_project_dir,
            self.preflight_job_id,
            self.preflight_log_dir,
            self.preflight_nextflow_log_name,
            self.preflight_job_name,
        )
        self.preflight_output = screen_output
        self.preflight_stderr_output = stderr_output
        self.preflight_nextflow_log = nextflow_log
        self.preflight_log_revision += 1
        if update_status:
            if self.preflight_job_id:
                self.status = f"Refreshed preflight log for {self.preflight_job_id}"
            else:
                self.status = "Refreshed preflight log"

    def refresh_preflight_log(self):
        self._refresh_preflight_log(update_status=True)
        yield

    def set_talos_project_dir(self, value: str):
        self.talos_project_dir = value
        self.talos_sbatch_script = str(Path(value.strip() or ".") / self.talos_log_dir / f"{self.talos_job_name}.sbatch")
        self.update_talos_command_preview()

    def set_talos_tool_dir(self, value: str):
        self.talos_tool_dir = value
        self.update_talos_command_preview()

    def set_talos_input_tsv(self, value: str):
        self.talos_input_tsv = value
        self.update_talos_command_preview()

    def set_talos_output_dir(self, value: str):
        self.talos_output_dir = value
        self.update_talos_command_preview()

    def set_talos_processed_annotations(self, value: str):
        self.talos_processed_annotations = value
        self.update_talos_command_preview()

    def set_talos_nextflow_config(self, value: str):
        self.talos_nextflow_config = value
        self.update_talos_command_preview()

    def set_talos_conda_env(self, value: str):
        self.talos_conda_env = value
        self.update_talos_command_preview()

    def set_talos_resume(self, value: bool):
        self.talos_resume = value
        self.update_talos_command_preview()

    def set_talos_spliceai_mode(self, value: str):
        self.talos_spliceai_mode = value
        self.update_talos_command_preview()

    def set_talos_spliceai_vcf(self, value: str):
        self.talos_spliceai_vcf = value
        self.update_talos_command_preview()

    def use_preflight_project_for_talos(self):
        self.set_talos_project_dir(self.preflight_project_dir)

    def update_talos_command_preview(self):
        self.talos_command_preview = runner.format_command_multiline(
            runner.build_talos_run_command(
                self.talos_project_dir,
                self.talos_tool_dir,
                self.talos_input_tsv,
                self.talos_output_dir,
                self.talos_processed_annotations,
                self.talos_nextflow_config,
                self.talos_conda_env,
                self.talos_resume,
                self.talos_spliceai_mode,
                self.talos_spliceai_vcf,
                self.talos_fastspliceai_bin,
                self.talos_fastspliceai_reference,
                self.talos_fastspliceai_cache,
                self.talos_fastspliceai_nextflow_config,
                self.talos_fastspliceai_queue,
                self.talos_fastspliceai_cluster_options,
                self.talos_fastspliceai_cpus,
                self.talos_fastspliceai_mem,
                self.talos_fastspliceai_time,
                self.talos_fastspliceai_annotation,
            ),
        )

    def refresh_talos_state(self):
        state = runner.slurm_job_state(self.talos_job_id)
        if state:
            self.talos_running = True
            self.talos_status = f"{state} {self.talos_job_id}"
            return

        job_id, job_state = runner.active_slurm_job(self.talos_job_name)
        if job_id:
            self.talos_job_id = job_id
            self.talos_running = True
            self.talos_status = f"{job_state} {job_id}"
            return

        if self.talos_running and self.talos_job_id:
            self.talos_status = f"Finished {self.talos_job_id}"
        self.talos_running = False

    def submit_talos(self):
        self.refresh_talos_state()
        if self.talos_running:
            self.status = f"TALOS already active: {self.talos_status}"
            yield
            return

        self.update_talos_command_preview()
        project_dir = Path(self.talos_project_dir)
        tool_dir = Path(self.talos_tool_dir)
        input_tsv = runner.project_path(self.talos_project_dir, self.talos_input_tsv)
        nextflow_config = runner.project_path(self.talos_project_dir, self.talos_nextflow_config)
        if not project_dir.is_dir():
            self.talos_status = "Missing"
            self.talos_output = f"Project folder does not exist: {project_dir}\n"
            self.status = self.talos_status
            yield
            return
        if not (tool_dir / "main.nf").exists():
            self.talos_status = "Missing"
            self.talos_output = f"TALOS workflow not found in: {tool_dir}\n"
            self.status = self.talos_status
            yield
            return
        if not input_tsv.exists():
            self.talos_status = "Missing"
            self.talos_output = f"TALOS input TSV does not exist: {input_tsv}\n"
            self.status = self.talos_status
            yield
            return
        if not nextflow_config.exists():
            self.talos_status = "Missing"
            self.talos_output = f"TALOS Nextflow config does not exist: {nextflow_config}\n"
            self.status = self.talos_status
            yield
            return
        if not TALOS_RUN_SCRIPT.exists():
            self.talos_status = "Missing"
            self.talos_output = f"TALOS wrapper does not exist: {TALOS_RUN_SCRIPT}\n"
            self.status = self.talos_status
            yield
            return

        self.talos_status = "Submitting"
        self.status = "Submitting TALOS"
        self.active_tab = "talos"
        self.talos_output = "$ sbatch <project>/logs/talos_full.sbatch\n\n"
        self.talos_stderr_output = ""
        self.talos_nextflow_log = ""
        yield

        try:
            output, job_id, script_path = runner.submit_talos_sbatch(
                self.talos_project_dir,
                self.talos_tool_dir,
                self.talos_input_tsv,
                self.talos_output_dir,
                self.talos_processed_annotations,
                self.talos_nextflow_config,
                self.talos_conda_env,
                self.talos_resume,
                self.talos_spliceai_mode,
                self.talos_spliceai_vcf,
                self.talos_fastspliceai_bin,
                self.talos_fastspliceai_reference,
                self.talos_fastspliceai_cache,
                self.talos_fastspliceai_nextflow_config,
                self.talos_fastspliceai_queue,
                self.talos_fastspliceai_cluster_options,
                self.talos_fastspliceai_cpus,
                self.talos_fastspliceai_mem,
                self.talos_fastspliceai_time,
                self.talos_fastspliceai_annotation,
                self.talos_log_dir,
                self.talos_job_name,
                self.talos_cpus,
                self.talos_mem,
                self.talos_time,
            )
            self.talos_job_id = job_id
            self.talos_sbatch_script = str(script_path)
            self.talos_output += output
            self.talos_output += f"\nsbatch script: {script_path}\n"
            if job_id:
                self.talos_running = True
                self.talos_status = f"Submitted {job_id}"
                self.status = self.talos_status
            else:
                self.talos_running = False
                self.talos_status = "Submit failed"
                self.status = self.talos_status
            yield
            self._refresh_talos_log(update_status=False)
            yield AppState.autorefresh_logs
        except Exception as error:
            self.talos_output += f"\nERROR: {error}\n"
            self.talos_status = "Failed"
            self.talos_running = False
            self.status = str(error)
            yield

    def cancel_talos(self):
        self.refresh_talos_state()
        if not self.talos_running or not self.talos_job_id:
            self.status = "No active TALOS job to cancel"
            yield
            return

        job_id = self.talos_job_id
        output = runner.cancel_slurm_job(job_id)
        if output:
            self.talos_output += output
        self.talos_running = False
        self.talos_status = f"Cancel requested {job_id}"
        self.status = self.talos_status
        yield
        self._refresh_talos_log(update_status=False)
        yield

    def _refresh_talos_log(self, update_status: bool):
        self.refresh_talos_state()
        screen_output, stderr_output, nextflow_log = runner.read_slurm_logs(
            self.talos_project_dir,
            self.talos_job_id,
            self.talos_log_dir,
            self.talos_job_name,
        )
        self.talos_output = screen_output
        self.talos_stderr_output = stderr_output
        self.talos_nextflow_log = nextflow_log
        self.talos_log_revision += 1
        if update_status:
            if self.talos_job_id:
                self.status = f"Refreshed TALOS log for {self.talos_job_id}"
            else:
                self.status = "Refreshed TALOS log"

    def refresh_talos_log(self):
        self._refresh_talos_log(update_status=True)
        yield
