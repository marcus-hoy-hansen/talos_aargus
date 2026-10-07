#!/usr/bin/env nextflow

nextflow.enable.dsl=2

include { MAP_SAMPLE_SHEET } from './modules/MapSampleSheet'
include { PREPARE_SINGLE_SAMPLE_VCF } from './modules/PrepareSingleSampleVcf'
include { FILTER_COMMON_DBSNP } from './modules/FilterCommonDbsnp'
include { BUILD_FAMILY_MERGE_PLAN } from './modules/BuildFamilyMergePlan'
include { MERGE_FAMILY_VCF } from './modules/MergeFamilyVcf'
include { MERGE_COHORT_VCFS } from './modules/MergeCohortVcfs'
include { ANNOTATE_COHORT_SPLICEAI } from './modules/AnnotateCohortSpliceAi'

def paramEnabled(value) {
    return value instanceof Boolean ? value : value?.toString()?.toBoolean()
}

workflow {
    main:
    if (!params.sample_manifest && !params.samplelist_xlsx) {
        println 'Provide either --sample_manifest with --pedigree, or --samplelist_xlsx'
        exit 1
    }

    if (params.sample_manifest && !params.pedigree) {
        println '--pedigree is required when using --sample_manifest'
        exit 1
    }

    def publishedFamilyDir = file("${workflow.outputDir}/family_vcfs")
    if (params.flush_published_family_vcfs && publishedFamilyDir.exists()) {
        if (!publishedFamilyDir.deleteDir()) {
            println "Failed to remove published family VCF directory: ${publishedFamilyDir}"
            exit 1
        }
    }

    def ch_manifest
    def ch_pedigree
    def ch_mapping_report = Channel.empty()

    if (params.samplelist_xlsx) {
        MAP_SAMPLE_SHEET(Channel.fromPath(params.samplelist_xlsx, checkIfExists: true))
        ch_manifest = MAP_SAMPLE_SHEET.out.manifest
        ch_pedigree = MAP_SAMPLE_SHEET.out.pedigree
        ch_mapping_report = MAP_SAMPLE_SHEET.out.report
    } else {
        ch_manifest = Channel.fromPath(params.sample_manifest, checkIfExists: true).first()
        ch_pedigree = Channel.fromPath(params.pedigree, checkIfExists: true).first()
    }

    ch_samples = ch_manifest
        .splitCsv(header: true, sep: '\t')
        .map { row -> tuple(row.sample_id, file(row.vcf_path, checkIfExists: true)) }

    PREPARE_SINGLE_SAMPLE_VCF(ch_samples)
    def ch_active_vcfs = PREPARE_SINGLE_SAMPLE_VCF.out.vcfs

    if (paramEnabled(params.common_dbsnp_enabled)) {
        if (!params.common_dbsnp_vcf) {
            println '--common_dbsnp_vcf is required when --common_dbsnp_enabled is true'
            exit 1
        }
        def common_dbsnp_idx = file("${params.common_dbsnp_vcf}.tbi")
        if (!common_dbsnp_idx.exists()) {
            common_dbsnp_idx = file("${params.common_dbsnp_vcf}.csi")
        }
        if (!common_dbsnp_idx.exists()) {
            println "Index not found for --common_dbsnp_vcf: ${params.common_dbsnp_vcf}.tbi or .csi"
            exit 1
        }
        FILTER_COMMON_DBSNP(
            ch_active_vcfs,
            Channel.fromPath(params.common_dbsnp_vcf, checkIfExists: true).first(),
            Channel.fromPath(common_dbsnp_idx, checkIfExists: true).first(),
        )
        ch_active_vcfs = FILTER_COMMON_DBSNP.out.vcf
    }

    ch_prepared_manifest = ch_active_vcfs
        .map { sample_id, vcf, _idx -> "${sample_id}\t${vcf}\n" }
        .collectFile(name: 'prepared_manifest.tsv', newLine: false, sort: true, seed: 'sample_id\tvcf_path\n')

    def ch_family_plan = Channel.empty()
    def ch_family_vcfs = Channel.empty()
    def ch_cohort_inputs

    if (paramEnabled(params.family_merge_enabled)) {
        BUILD_FAMILY_MERGE_PLAN(ch_pedigree, ch_prepared_manifest)
        ch_family_plan = BUILD_FAMILY_MERGE_PLAN.out.plan

        ch_family_tasks = ch_family_plan
            .splitCsv(header: true, sep: '\t')
            .map { row ->
                tuple(
                    row.family_id,
                    row.proband_id,
                    row.output_name,
                    row.input_vcfs.tokenize('|').collect { file(it, checkIfExists: true) },
                )
            }

        MERGE_FAMILY_VCF(ch_family_tasks)
        ch_family_vcfs = MERGE_FAMILY_VCF.out.family_vcfs
        ch_cohort_inputs = ch_family_vcfs.map { _family_id, vcf, _idx -> vcf }
    } else {
        ch_cohort_inputs = ch_active_vcfs.map { _sample_id, vcf, _idx -> vcf }
    }

    MERGE_COHORT_VCFS(ch_cohort_inputs.collect())

    def ch_final_cohort = MERGE_COHORT_VCFS.out.vcf

    if (paramEnabled(params.spliceai_enabled)) {
        if (!params.spliceai_vcf) {
            println '--spliceai_vcf is required when --spliceai_enabled is true'
            exit 1
        }
        ANNOTATE_COHORT_SPLICEAI(
            ch_final_cohort,
            Channel.fromPath(params.spliceai_vcf, checkIfExists: true).first(),
        )
        ch_final_cohort = ANNOTATE_COHORT_SPLICEAI.out.vcf
    }

    def ch_talos_input = Channel.empty()
    if (paramEnabled(params.talos_input_enabled)) {
        if (!params.talos_config) {
            println '--talos_config is required when --talos_input_enabled is true'
            exit 1
        }
        ch_talos_input = ch_final_cohort
            .combine(ch_pedigree)
            .map { cohort_vcf, cohort_vcf_idx, pedigree ->
                def published_vcf = "${workflow.outputDir}/${cohort_vcf.name}"
                def published_pedigree = "${workflow.outputDir}/${pedigree.name}"
                def talos_cohort = params.talos_cohort ?: params.department
                [
                    'cohort\tpath\ttype\tpedigree\tconfig\thistory\text_ids\tseqr_map\tmito\n',
                    "${talos_cohort}\t${published_vcf}\t${params.talos_variant_type}\t${published_pedigree}\t${params.talos_config}\t${params.talos_history}\t${params.talos_ext_ids}\t${params.talos_seqr_map}\t${params.talos_mito}\n",
                ].join('')
            }
            .collectFile(name: 'talos_input.tsv', newLine: false)
    }

    publish:
    manifest = ch_prepared_manifest
    pedigree = ch_pedigree
    family_plan = ch_family_plan
    family_vcfs = paramEnabled(params.family_merge_enabled) && paramEnabled(params.publish_family_vcfs) ? ch_family_vcfs : Channel.empty()
    cohort_vcf = ch_final_cohort
    mapping_report = ch_mapping_report
    talos_input = ch_talos_input
}

output {
    manifest {
        path { manifest_file -> '.' }
    }
    pedigree {
        path { pedigree_file -> '.' }
    }
    family_plan {
        path { plan_file -> '.' }
    }
    family_vcfs {
        path { family_id, family_vcf, family_idx -> 'family_vcfs' }
    }
    cohort_vcf {
        path { cohort_vcf_file, cohort_vcf_idx -> '.' }
    }
    mapping_report {
        path { mapping_report_file -> '.' }
    }
    talos_input {
        path { talos_input_file -> '.' }
    }
}
