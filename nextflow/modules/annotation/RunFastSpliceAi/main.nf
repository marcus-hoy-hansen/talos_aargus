process RunFastSpliceAi {
    tag "$cohort"

    input:
    tuple val(cohort), path(vcf), path(vcf_index), path(cache_misses), path(cache_misses_index), path(cache_status)
    val reference_fasta

    output:
    tuple val(cohort), path(vcf), path(vcf_index), path("cache_additions.vcf.gz"), path("cache_additions.vcf.gz.tbi"), emit: additions

    when:
    cache_status.getText().trim().toInteger() > 0

    script:
    """
    set -euo pipefail

    test -x "${params.fastspliceai_bin}"
    test -f "${reference_fasta}"
    test -f "${reference_fasta}.fai"
    annotation="${params.fastspliceai_annotation ?: 'grch38'}"
    if [[ "\${annotation}" != "grch37" && "\${annotation}" != "grch38" ]]; then
        test -f "\${annotation}"
    fi

    "${params.fastspliceai_bin}" \\
        -I "${cache_misses}" \\
        -O cache_additions.vcf.gz \\
        -R "${reference_fasta}" \\
        -A "\${annotation}" \\
        --output-type z \\
        --write-index=tbi \\
        --overwrite-existing \\
        --device cuda \\
        --threads "${task.cpus}"
    """
}
