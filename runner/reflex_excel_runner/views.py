import reflex as rx

from .paths import UPLOAD_ID
from .state import AppState


def nav_button(label: str, tab: str) -> rx.Component:
    return rx.button(
        label,
        on_click=lambda: AppState.set_tab(tab),
        variant=rx.cond(AppState.active_tab == tab, "solid", "soft"),
        size="3",
    )


def page_shell(content: rx.Component) -> rx.Component:
    return rx.vstack(
        log_autoscroll_script(),
        rx.hstack(
            rx.heading("TALOS AARGUS TEST RUNNER", size="6"),
            rx.spacer(),
            rx.badge(AppState.status, variant="soft"),
            width="100%",
            align="center",
        ),
        rx.hstack(
            nav_button("Import", "import"),
            nav_button("Config", "config"),
            nav_button("Resources", "resources"),
            nav_button("Preparation", "preparation"),
            nav_button("Preflight", "preflight"),
            nav_button("TALOS", "talos"),
            spacing="3",
        ),
        rx.box(content, width="100%"),
        spacing="5",
        width="100%",
        max_width="1180px",
        margin="0 auto",
        padding="24px",
        font_family="Arial, Segoe UI, sans-serif",
    )


def log_autoscroll_script() -> rx.Component:
    return rx.script(
        """
        (() => {
          const ids = [
            "preflight-screen-log",
            "preflight-stderr-log",
            "preflight-nextflow-log",
            "talos-screen-log",
            "talos-stderr-log",
            "talos-nextflow-log",
          ];
          const seen = {};
          const scrollChangedLogs = () => {
            for (const id of ids) {
              const field = document.getElementById(id);
              if (!field) continue;
              const value = field.value || "";
              const key = `${value.length}:${field.scrollHeight}`;
              if (seen[id] !== key) {
                seen[id] = key;
                field.scrollTop = field.scrollHeight;
              }
            }
          };
          if (!window.__talosLogAutoscroll) {
            window.__talosLogAutoscroll = window.setInterval(scrollChangedLogs, 1000);
          }
          scrollChangedLogs();
        })();
        """
    )


def table_card(title: str, columns, rows) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(title, size="4"),
            rx.data_table(
                data=rows,
                columns=columns,
                search=True,
                sort=True,
                pagination=True,
                resizable=True,
                width="100%",
            ),
            spacing="3",
            align="stretch",
        ),
        width="100%",
    )


def import_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Load Excel", size="4"),
                rx.upload(
                    rx.vstack(
                        rx.text("Drop an .xlsx file here or click to choose one."),
                        rx.text(rx.selected_files(UPLOAD_ID), color="gray"),
                        spacing="2",
                    ),
                    id=UPLOAD_ID,
                    multiple=False,
                    accept={
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
                            ".xlsx"
                        ]
                    },
                    border="1px dashed #999",
                    border_radius="8px",
                    padding="28px",
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "Upload",
                        on_click=AppState.handle_upload(rx.upload_files(upload_id=UPLOAD_ID)),
                    ),
                    rx.button("Load sample", on_click=AppState.load_sample, variant="soft"),
                    rx.text(AppState.uploaded_file, color="gray"),
                    width="100%",
                    align="center",
                ),
                spacing="4",
                align="stretch",
            ),
            width="100%",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Edit Excel", size="4"),
                rx.text_area(
                    value=AppState.excel_editor_text,
                    on_change=AppState.set_excel_editor_text,
                    placeholder="Header row, then one tab-delimited row per sample.",
                    height="320px",
                    width="100%",
                    font_family="Consolas, monospace",
                ),
                config_field(
                    "Output Excel file",
                    AppState.excel_output_path,
                    AppState.set_excel_output_path,
                ),
                rx.hstack(
                    rx.button("Add blank row", on_click=AppState.add_excel_row, variant="soft"),
                    rx.input(
                        value=AppState.excel_delete_row,
                        on_change=AppState.set_excel_delete_row,
                        placeholder="Data row number",
                        width="160px",
                    ),
                    rx.button(
                        "Delete row",
                        on_click=AppState.delete_excel_row_by_index,
                        variant="soft",
                        color_scheme="red",
                    ),
                    rx.button("Save Excel", on_click=AppState.save_edited_excel),
                    align="center",
                ),
                spacing="3",
                align="stretch",
            ),
            width="100%",
        ),
        rx.cond(
            AppState.has_preview,
            table_card("Preview", AppState.preview_columns, AppState.preview_rows),
            rx.callout("No preview loaded yet.", icon="info"),
        ),
        spacing="4",
        align="stretch",
    )


def config_field(label: str, value, setter, placeholder: str = "") -> rx.Component:
    return rx.vstack(
        rx.text(label, weight="bold"),
        rx.input(value=value, on_change=setter, placeholder=placeholder, width="100%"),
        spacing="1",
        align="stretch",
    )


def config_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Runner Config", size="4"),
                rx.hstack(
                    rx.text(AppState.config_path, color="gray"),
                    rx.spacer(),
                    rx.button("Choose config", on_click=AppState.open_config_dialog, variant="soft"),
                    align="center",
                    width="100%",
                ),
                rx.text_area(
                    value=AppState.config_text,
                    on_change=AppState.set_config_text,
                    height="520px",
                    width="100%",
                    font_family="Consolas, monospace",
                ),
                rx.hstack(
                    rx.button("Save config", on_click=AppState.save_config),
                    rx.button("Reload config", on_click=AppState.reload_config, variant="soft"),
                    align="center",
                ),
                spacing="4",
                align="stretch",
            ),
            width="100%",
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.vstack(
                    rx.dialog.title("Choose runner.config"),
                    rx.dialog.description(
                        "Selecting a config reloads Resources, Preparation, Preflight, and TALOS."
                    ),
                    rx.select(
                        AppState.config_candidates,
                        value=AppState.config_candidate,
                        on_change=AppState.set_config_candidate,
                        width="100%",
                    ),
                    config_field(
                        "Config file",
                        AppState.config_candidate,
                        AppState.set_config_candidate,
                    ),
                    rx.hstack(
                        rx.button("Cancel", on_click=AppState.close_config_dialog, variant="soft"),
                        rx.button("Load config", on_click=AppState.apply_config_candidate),
                        justify="end",
                        width="100%",
                    ),
                    spacing="3",
                    align="stretch",
                ),
            ),
            open=AppState.config_dialog_open,
            on_open_change=AppState.set_config_dialog_open,
        ),
        spacing="4",
        align="stretch",
        width="100%",
    )


def resources_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Resources", size="4"),
                rx.text("Download resources script", weight="bold"),
                rx.code(AppState.resource_script_path, white_space="pre-wrap", width="100%"),
                rx.hstack(
                    rx.button(
                        "Run resource download",
                        on_click=AppState.run_resource_download,
                    ),
                    rx.button(
                        "Refresh path",
                        on_click=AppState.refresh_resource_script,
                        variant="soft",
                    ),
                    rx.badge(AppState.resource_status, variant="soft"),
                    align="center",
                ),
                rx.code(
                    AppState.resource_command_preview,
                    white_space="pre-wrap",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
            ),
            width="100%",
        ),
        rx.text_area(
            value=AppState.resource_output,
            read_only=True,
            height="520px",
            width="100%",
            font_family="Consolas, monospace",
        ),
        spacing="4",
        align="stretch",
    )


def preparation_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Preparation", size="4"),
                config_field(
                    "Working directory",
                    AppState.preparation_work_dir,
                    AppState.set_preparation_work_dir,
                ),
                config_field(
                    "Processed annotations",
                    AppState.preparation_processed_annotations,
                    AppState.set_preparation_processed_annotations,
                ),
                config_field(
                    "Large files",
                    AppState.preparation_large_files,
                    AppState.set_preparation_large_files,
                ),
                config_field(
                    "Environment prefix",
                    AppState.preparation_env_prefix,
                    AppState.set_preparation_env_prefix,
                ),
                rx.hstack(
                    rx.button(
                        "Run preparation",
                        on_click=AppState.run_preparation,
                    ),
                    rx.button(
                        "Refresh command",
                        on_click=AppState.update_preparation_command_preview,
                        variant="soft",
                    ),
                    rx.badge(AppState.preparation_status, variant="soft"),
                    align="center",
                ),
                rx.code(
                    AppState.preparation_command_preview,
                    white_space="pre-wrap",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
            ),
            width="100%",
        ),
        rx.text_area(
            value=AppState.preparation_output,
            read_only=True,
            height="520px",
            width="100%",
            font_family="Consolas, monospace",
        ),
        spacing="4",
        align="stretch",
    )


def preflight_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("Project", size="4"),
                rx.hstack(
                    rx.vstack(
                        rx.text("Project", weight="bold"),
                        rx.text(AppState.preflight_project_dir, font_family="Consolas, monospace"),
                        spacing="1",
                        align="start",
                        width="100%",
                    ),
                    rx.button(
                        "Choose project",
                        on_click=AppState.open_preflight_project_dialog,
                        variant="soft",
                    ),
                    align="center",
                    width="100%",
                ),
                config_field(
                    "Excel sample list",
                    AppState.preflight_samplelist,
                    AppState.set_preflight_samplelist,
                ),
                rx.vstack(
                    rx.text("Source VCF folder(s)", weight="bold"),
                    rx.text_area(
                        value=AppState.preflight_source_vcf_folder,
                        on_change=AppState.set_preflight_source_vcf_folder,
                        placeholder="Optional. One folder per line, or leave empty for parser auto-detection.",
                        height="84px",
                        width="100%",
                    ),
                    spacing="1",
                    align="stretch",
                ),
                rx.hstack(
                    rx.button(
                        "Use parser auto",
                        on_click=AppState.clear_preflight_source_vcf_folder,
                        variant="soft",
                    ),
                    align="center",
                ),
                config_field(
                    "Department",
                    AppState.preflight_department,
                    AppState.set_preflight_department,
                ),
                rx.checkbox(
                    "Resume Nextflow",
                    checked=AppState.preflight_resume,
                    on_change=AppState.set_preflight_resume,
                ),
                config_field(
                    "TALOS cohort label",
                    AppState.preflight_talos_cohort,
                    AppState.set_preflight_talos_cohort,
                ),
                config_field(
                    "TALOS config",
                    AppState.preflight_talos_config,
                    AppState.set_preflight_talos_config,
                ),
                rx.checkbox(
                    "Legacy preflight SpliceAI",
                    checked=AppState.preflight_spliceai_enabled,
                    on_change=AppState.set_preflight_spliceai_enabled,
                ),
                config_field(
                    "Preflight SpliceAI VCF",
                    AppState.preflight_spliceai_vcf,
                    AppState.set_preflight_spliceai_vcf,
                ),
                rx.hstack(
                    rx.button(
                        "Submit preflight",
                        on_click=AppState.submit_preflight,
                        disabled=AppState.preflight_running,
                    ),
                    rx.cond(
                        AppState.preflight_running,
                        rx.button(
                            "Cancel preflight",
                            on_click=AppState.cancel_preflight,
                            color_scheme="red",
                            variant="soft",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        "Refresh log",
                        on_click=AppState.refresh_preflight_log,
                        variant="soft",
                    ),
                    rx.button(
                        "Refresh command",
                        on_click=AppState.update_preflight_command_preview,
                        variant="soft",
                    ),
                    rx.badge(AppState.preflight_status, variant="soft"),
                    align="center",
                ),
                rx.text("Slurm job", weight="bold"),
                rx.code(AppState.preflight_job_id, white_space="pre-wrap", width="100%"),
                rx.text("sbatch script", weight="bold"),
                rx.code(AppState.preflight_sbatch_script, white_space="pre-wrap", width="100%"),
                rx.text("Command preview", weight="bold"),
                rx.code(
                    AppState.preflight_command_preview,
                    white_space="pre-wrap",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
            ),
            width="100%",
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.vstack(
                    rx.dialog.title("Choose project"),
                    rx.dialog.description(
                        "This changes the project for this browser session only. runner.config is unchanged."
                    ),
                    rx.select(
                        AppState.preflight_project_choices,
                        value=AppState.preflight_project_candidate,
                        on_change=AppState.set_preflight_project_candidate,
                        width="100%",
                    ),
                    config_field(
                        "Project folder",
                        AppState.preflight_project_candidate,
                        AppState.set_preflight_project_candidate,
                    ),
                    rx.hstack(
                        rx.button("Cancel", on_click=AppState.close_preflight_project_dialog, variant="soft"),
                        rx.button("Use project", on_click=AppState.apply_preflight_project_candidate),
                        justify="end",
                        width="100%",
                    ),
                    spacing="3",
                    align="stretch",
                ),
            ),
            open=AppState.preflight_project_dialog_open,
            on_open_change=AppState.set_preflight_project_dialog_open,
        ),
        rx.vstack(
            rx.heading("Nextflow Screen Output", size="3"),
            rx.text_area(
                id="preflight-screen-log",
                key=AppState.preflight_log_revision,
                value=AppState.preflight_output,
                read_only=True,
                height="340px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        rx.vstack(
            rx.heading("Slurm Stderr / Warnings", size="3"),
            rx.text_area(
                id="preflight-stderr-log",
                key=AppState.preflight_log_revision,
                value=AppState.preflight_stderr_output,
                read_only=True,
                height="180px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        rx.vstack(
            rx.heading("Nextflow Log Tail", size="3"),
            rx.text_area(
                id="preflight-nextflow-log",
                key=AppState.preflight_log_revision,
                value=AppState.preflight_nextflow_log,
                read_only=True,
                height="260px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        spacing="4",
        align="stretch",
    )


def talos_view() -> rx.Component:
    return rx.vstack(
        rx.card(
            rx.vstack(
                rx.heading("TALOS", size="4"),
                config_field(
                    "Project / reanalysis folder",
                    AppState.talos_project_dir,
                    AppState.set_talos_project_dir,
                ),
                rx.hstack(
                    rx.button(
                        "Use Preflight project",
                        on_click=AppState.use_preflight_project_for_talos,
                        variant="soft",
                    ),
                    align="center",
                ),
                config_field(
                    "TALOS tool folder",
                    AppState.talos_tool_dir,
                    AppState.set_talos_tool_dir,
                ),
                config_field(
                    "Input TSV",
                    AppState.talos_input_tsv,
                    AppState.set_talos_input_tsv,
                ),
                config_field(
                    "Output folder",
                    AppState.talos_output_dir,
                    AppState.set_talos_output_dir,
                ),
                config_field(
                    "Processed annotations",
                    AppState.talos_processed_annotations,
                    AppState.set_talos_processed_annotations,
                ),
                config_field(
                    "Nextflow config",
                    AppState.talos_nextflow_config,
                    AppState.set_talos_nextflow_config,
                ),
                config_field(
                    "Conda environment",
                    AppState.talos_conda_env,
                    AppState.set_talos_conda_env,
                ),
                rx.select(
                    ["disabled", "precomputed", "fastspliceai", "fastspliceai_cache"],
                    value=AppState.talos_spliceai_mode,
                    on_change=AppState.set_talos_spliceai_mode,
                    width="100%",
                ),
                rx.cond(
                    AppState.talos_spliceai_mode == "precomputed",
                    config_field(
                        "SpliceAI VCF",
                        AppState.talos_spliceai_vcf,
                        AppState.set_talos_spliceai_vcf,
                    ),
                ),
                rx.checkbox(
                    "Resume Nextflow",
                    checked=AppState.talos_resume,
                    on_change=AppState.set_talos_resume,
                ),
                rx.hstack(
                    rx.button(
                        "Submit TALOS",
                        on_click=AppState.submit_talos,
                        disabled=AppState.talos_running,
                    ),
                    rx.cond(
                        AppState.talos_running,
                        rx.button(
                            "Cancel TALOS",
                            on_click=AppState.cancel_talos,
                            color_scheme="red",
                            variant="soft",
                        ),
                        rx.fragment(),
                    ),
                    rx.button(
                        "Refresh log",
                        on_click=AppState.refresh_talos_log,
                        variant="soft",
                    ),
                    rx.button(
                        "Refresh command",
                        on_click=AppState.update_talos_command_preview,
                        variant="soft",
                    ),
                    rx.badge(AppState.talos_status, variant="soft"),
                    align="center",
                ),
                rx.text("Slurm job", weight="bold"),
                rx.code(AppState.talos_job_id, white_space="pre-wrap", width="100%"),
                rx.text("sbatch script", weight="bold"),
                rx.code(AppState.talos_sbatch_script, white_space="pre-wrap", width="100%"),
                rx.text("Command preview", weight="bold"),
                rx.code(
                    AppState.talos_command_preview,
                    white_space="pre-wrap",
                    width="100%",
                ),
                spacing="3",
                align="stretch",
            ),
            width="100%",
        ),
        rx.vstack(
            rx.heading("TALOS Screen Output", size="3"),
            rx.text_area(
                id="talos-screen-log",
                key=AppState.talos_log_revision,
                value=AppState.talos_output,
                read_only=True,
                height="360px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        rx.vstack(
            rx.heading("Slurm Stderr / Warnings", size="3"),
            rx.text_area(
                id="talos-stderr-log",
                key=AppState.talos_log_revision,
                value=AppState.talos_stderr_output,
                read_only=True,
                height="200px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        rx.vstack(
            rx.heading("Nextflow Log Tail", size="3"),
            rx.text_area(
                id="talos-nextflow-log",
                key=AppState.talos_log_revision,
                value=AppState.talos_nextflow_log,
                read_only=True,
                height="260px",
                width="100%",
                font_family="Consolas, monospace",
            ),
            spacing="2",
            align="stretch",
        ),
        spacing="4",
        align="stretch",
    )


def index() -> rx.Component:
    return page_shell(
        rx.cond(
            AppState.active_tab == "import",
            import_view(),
            rx.cond(
                AppState.active_tab == "config",
                config_view(),
                rx.cond(
                    AppState.active_tab == "resources",
                    resources_view(),
                    rx.cond(
                        AppState.active_tab == "preparation",
                        preparation_view(),
                        rx.cond(
                            AppState.active_tab == "preflight",
                            preflight_view(),
                            talos_view(),
                        ),
                    ),
                ),
            ),
        )
    )
