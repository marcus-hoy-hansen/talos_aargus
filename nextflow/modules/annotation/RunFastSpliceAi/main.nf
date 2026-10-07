process RunFastSpliceAi {
    tag "$cohort"

    input:
    tuple val(cohort), path(vcf), path(vcf_index), path(cache_misses), path(cache_misses_index), path(cache_status)
    val reference_fasta

    output:
    tuple val(cohort), path(vcf), path(vcf_index), path("cache_additions.vcf.gz"), path("cache_additions.vcf.gz.tbi"), emit: additions

    when:
    cache_status.text.trim().toInteger() > 0

    script:
    """
    set -euo pipefail

    test -x "${params.fastspliceai_bin}"
    test -f "${reference_fasta}"
    test -f "${reference_fasta}.fai"

    "${params.fastspliceai_bin}" \\
        -I "${cache_misses}" \\
        -O cache_additions.vcf.gz \\
        -R "${reference_fasta}" \\
        -A grch38 \\
        --output-type z \\
        --write-index=tbi \\
        --overwrite-existing \\
        --device cuda \\
        --threads "${task.cpus}"
    """
}
