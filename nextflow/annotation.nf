#!/usr/bin/env nextflow

nextflow.enable.dsl=2

/*
This workflow is the annotation process for the Talos pipeline.

It requires a single VCF, which can be single- or multi-sample. This is then annotated and reformatted for Talos.
The specific annotations are:

- gnomAD v4.1 frequencies and alphamissense annotations, applied to the joint VCF using echtvar
- Transcript consequences, using BCFtools annotate
- MANE trancript IDs and corresponding ENSP IDs, applied using Hail
*/

include { AnnotateCsqWithBcftools } from './modules/annotation/AnnotateCsqWithBcftools/main'
include { AnnotateWithEchtvar } from './modules/annotation/AnnotateWithEchtvar/main'
include { AnnotateWithFastSpliceAi } from './modules/annotation/AnnotateWithFastSpliceAi/main'
include { AnnotateFastSpliceAiFromCache } from './modules/annotation/AnnotateFastSpliceAiFromCache/main'
include { AnnotateWithSpliceAi } from './modules/annotation/AnnotateWithSpliceAi/main'
include { CheckFastSpliceAiCache } from './modules/annotation/CheckFastSpliceAiCache/main'
include { IndexVcf } from './modules/annotation/IndexVcf/main'
include { MergeFastSpliceAiCache } from './modules/annotation/MergeFastSpliceAiCache/main'
include { MergeVcfsWithBcftools } from './modules/annotation/MergeVcfsWithBcftools/main'
include { NormaliseAndRegionFilterVcf } from './modules/annotation/NormaliseAndRegionFilterVcf/main'
include { RunFastSpliceAi } from './modules/annotation/RunFastSpliceAi/main'
include { SplitVcf } from './modules/annotation/SplitVcf/main'

def processedAnnotationPath(String name) {
    return file("${params.processed_annotations}/${name}")
}

def paramEnabled(value) {
    return value instanceof Boolean ? value : value?.toString()?.toBoolean()
}

def spliceaiMode() {
    if (params.spliceai_mode) {
        def mode = params.spliceai_mode.toString().toLowerCase()
        if (!(mode in ['precomputed', 'fastspliceai', 'fastspliceai_cache', 'disabled'])) {
            println "Invalid --spliceai_mode: ${params.spliceai_mode}. Use precomputed, fastspliceai, fastspliceai_cache, or disabled."
            exit 1
        }
        return mode
    }
    return paramEnabled(params.spliceai_enabled) ? 'precomputed' : 'disabled'
}

workflow ANNOTATION {
	take:
		ch_gff
		ch_mane
		ch_ref_genome
		ch_inputs

    main:
    // populate various input channels - these are downloaded by the large_files/gather_files.sh script, or the prep wf
    def alphamissense_zip = processedAnnotationPath('alphamissense.zip')
    def ensembl_bed = processedAnnotationPath('GRCh38.bed')
    def ensembl_merged_bed = processedAnnotationPath('GRCh38_merged.bed')

    if (!alphamissense_zip.exists()) {
        println "AlphaMissense data must be encoded for echtvar, run the Talos Prep workflow (talos_preparation.nf)"
        exit 1
    }
    ch_alphamissense_zip = channel.fromPath(alphamissense_zip, checkIfExists: true).first()

    // check the ensembl BED file has been generated
    if (!ensembl_bed.exists()) {
        println "Region-Of-Interest BED file has not been prepared, run the Talos Prep workflow (talos_preparation.nf)"
        exit 1
    }
    ch_bed = channel.fromPath(ensembl_bed, checkIfExists: true).first()
    ch_merged_bed = channel.fromPath(ensembl_merged_bed, checkIfExists: true).first()

    ch_gnomad_zip = channel.fromPath(params.gnomad_zip, checkIfExists: true).first()

    ch_inputs_branched = ch_inputs.branch {
        shards: it[2] == 'shards'
        vcf_dir: it[2] == 'ss_vcf_dir'
        single_vcf: it[2] == 'vcf'
    }

    def spliceai_mode = spliceaiMode()

    // Process shards
    ch_from_shards = ch_inputs_branched.shards.flatMap { cohort, path, _type ->
        def vcfs = files("${path}/*.${params.input_vcf_extension}")
        vcfs.collect { vcf -> tuple(cohort, vcf) }
    }

    // Process single-sample components
    ch_vcf_dir_inputs = ch_inputs_branched.vcf_dir.map { cohort, path, _type ->
        def vcfs = files("${path}/*.${params.input_vcf_extension}")
        def tbis = vcfs.collect { file("${it}.tbi") }
        tuple(cohort, vcfs, tbis)
    }

    MergeVcfsWithBcftools(
        ch_vcf_dir_inputs,
        ch_ref_genome,
    )
    ch_merged_vcfs = MergeVcfsWithBcftools.out

    // Process single VCF
    ch_single_vcfs = ch_inputs_branched.single_vcf.map { cohort, path, _type ->
        tuple(cohort, file(path, checkIfExists: true))
    }

    // Combine single VCFs and merged VCFs. FastSpliceAI is deliberately run
    // here as one cohort job, after ROI normalization and before splitting.
    ch_collective_vcfs = ch_single_vcfs.mix(ch_merged_vcfs)

    if (spliceai_mode in ['fastspliceai', 'fastspliceai_cache']) {
        if (!params.fastspliceai_bin) {
            println '--fastspliceai_bin is required when --spliceai_mode fastspliceai'
            exit 1
        }
        def fastspliceai_reference = params.fastspliceai_reference ?: params.ref_genome
        if (!file(fastspliceai_reference).exists()) {
            println "FastSpliceAI reference does not exist: ${fastspliceai_reference}"
            exit 1
        }
        if (!file("${fastspliceai_reference}.fai").exists()) {
            println "FastSpliceAI reference index does not exist: ${fastspliceai_reference}.fai"
            exit 1
        }
        def fastspliceai_cache = ''
        if (spliceai_mode == 'fastspliceai_cache') {
            if (!params.fastspliceai_cache) {
                println '--fastspliceai_cache is required when --spliceai_mode fastspliceai_cache'
                exit 1
            }
            fastspliceai_cache = file(params.fastspliceai_cache).toString()
        }

        NormaliseAndRegionFilterVcf(
            ch_collective_vcfs,
            ch_merged_bed,
            ch_ref_genome,
        )
        if (spliceai_mode == 'fastspliceai') {
            AnnotateWithFastSpliceAi(
                NormaliseAndRegionFilterVcf.out,
                channel.value(file(fastspliceai_reference).toString()),
                channel.value(''),
            )
            ch_fastspliceai_vcfs = AnnotateWithFastSpliceAi.out
        } else {
            CheckFastSpliceAiCache(
                NormaliseAndRegionFilterVcf.out,
                channel.value(file(fastspliceai_cache).toString()),
            )
            def checked = CheckFastSpliceAiCache.out.checked
            def cache_hits = checked.filter { it[7].text.trim() == '0' }
            def cache_misses = checked.filter { it[7].text.trim() != '0' }

            AnnotateFastSpliceAiFromCache(
                cache_hits.map { cohort, vcf, vcf_index, sites, sites_index, misses, misses_index, status ->
                    tuple(cohort, vcf, vcf_index)
                },
                channel.value(file(fastspliceai_cache).toString()),
            )
            RunFastSpliceAi(
                cache_misses.map { cohort, vcf, vcf_index, sites, sites_index, misses, misses_index, status ->
                    tuple(cohort, vcf, vcf_index, misses, misses_index, status)
                },
                channel.value(file(fastspliceai_reference).toString()),
            )
            MergeFastSpliceAiCache(
                RunFastSpliceAi.out.additions,
                channel.value(file(fastspliceai_cache).toString()),
            )
            ch_fastspliceai_vcfs = AnnotateFastSpliceAiFromCache.out.annotated.mix(MergeFastSpliceAiCache.out.annotated)
        }

        if ((params.vcf_split_n ?: 0) > 0) {
            SplitVcf(ch_fastspliceai_vcfs.map { cohort, vcf, fastspliceai_index -> tuple(cohort, vcf) })
            ch_fastspliceai_splits = SplitVcf.out.flatMap { cohort, splits ->
                def split_list = splits instanceof Collection ? splits : [splits]
                split_list.collect { tuple(cohort, it) }
            }
            IndexVcf(ch_fastspliceai_splits)
            ch_all_vcfs = IndexVcf.out
        } else {
            ch_all_vcfs = ch_fastspliceai_vcfs
        }

        // FastSpliceAI must see one cohort VCF. Existing split inputs are not
        // equivalent and are therefore rejected rather than partly annotated.
        ch_all_vcfs = ch_all_vcfs.mix(ch_inputs_branched.shards.map { ignored_shard ->
            throw new IllegalArgumentException('FastSpliceAI modes do not support input type shards')
        })
    } else {
        if ((params.vcf_split_n ?: 0) > 0) {
            SplitVcf(ch_collective_vcfs)
            ch_vcfs = SplitVcf.out.flatMap { cohort, splits ->
                def split_list = splits instanceof Collection ? splits : [splits]
                split_list.collect { tuple(cohort, it) }
            }
        } else {
            ch_vcfs = ch_collective_vcfs
        }
        ch_all_vcfs = ch_vcfs.mix(ch_from_shards)

	    NormaliseAndRegionFilterVcf(
            ch_all_vcfs,
            ch_merged_bed,
            ch_ref_genome,
        )
        ch_all_vcfs = NormaliseAndRegionFilterVcf.out
    }

	AnnotateWithEchtvar(
        ch_all_vcfs,
        ch_gnomad_zip,
        ch_alphamissense_zip,
    )

    // annotate transcript consequences with bcftools csq
    AnnotateCsqWithBcftools(
        AnnotateWithEchtvar.out,
        ch_gff,
        ch_ref_genome,
    )

    ch_annotated_vcfs = AnnotateCsqWithBcftools.out

    if (spliceai_mode == 'precomputed') {
        if (!params.spliceai_vcf) {
            println '--spliceai_vcf is required when --spliceai_enabled is true'
            exit 1
        }
        def spliceai_vcf_idx = file("${params.spliceai_vcf}.tbi")
        if (!spliceai_vcf_idx.exists()) {
            spliceai_vcf_idx = file("${params.spliceai_vcf}.csi")
        }
        if (!spliceai_vcf_idx.exists()) {
            println "Index not found for --spliceai_vcf: ${params.spliceai_vcf}.tbi or .csi"
            exit 1
        }
        AnnotateWithSpliceAi(
            ch_annotated_vcfs,
            channel.fromPath(params.spliceai_vcf, checkIfExists: true).first(),
            channel.fromPath(spliceai_vcf_idx, checkIfExists: true).first(),
        )
        ch_annotated_vcfs = AnnotateWithSpliceAi.out
    }

    emit:
	vcfs = ch_annotated_vcfs.groupTuple(by: 0)
}
