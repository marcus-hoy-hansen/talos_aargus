process MergeFastSpliceAiCache {
    tag "$cohort"

    input:
    tuple val(cohort), path(vcf), path(vcf_index), path(cache_additions), path(cache_additions_index)
    val cache_vcf

    output:
    tuple val(cohort), path("${vcf.simpleName}_fastspliceai.vcf.gz"), path("${vcf.simpleName}_fastspliceai.vcf.gz.tbi"), emit: annotated

    script:
    """
    set -euo pipefail
    umask 002

    output_vcf="${vcf.simpleName}_fastspliceai.vcf.gz"
    mkdir -p "\$(dirname "${cache_vcf}")"
    cache_tmp="\$(mktemp "${cache_vcf}.tmp.XXXXXX")"

    (
        flock -x 9
        if [[ -f "${cache_vcf}" ]]; then
            bcftools view -G -Ou "${cache_additions}" \\
                | bcftools annotate -x '^INFO/SpliceAI' -Oz -o cache_additions.sites.vcf.gz
            tabix -f -p vcf cache_additions.sites.vcf.gz
            bcftools concat -a "${cache_vcf}" cache_additions.sites.vcf.gz -Ou \\
                | bcftools sort -Ou \\
                | bcftools norm -d exact -Oz -o "\${cache_tmp}"
        else
            bcftools view -G -Ou "${cache_additions}" \\
                | bcftools annotate -x '^INFO/SpliceAI' -Oz -o "\${cache_tmp}"
        fi
        tabix -f -p vcf "\${cache_tmp}"
        mv -f "\${cache_tmp}" "${cache_vcf}"
        mv -f "\${cache_tmp}.tbi" "${cache_vcf}.tbi"
    ) 9>"${cache_vcf}.lock"

    bcftools annotate -a "${cache_vcf}" -c INFO/SpliceAI \\
        -Oz -o "\${output_vcf}" "${vcf}"
    tabix -f -p vcf "\${output_vcf}"
    """
}
