process AnnotateFastSpliceAiFromCache {
    tag "$cohort"

    input:
    tuple val(cohort), path(vcf), path(vcf_index)
    val cache_vcf

    output:
    tuple val(cohort), path("${vcf.simpleName}_fastspliceai.vcf.gz"), path("${vcf.simpleName}_fastspliceai.vcf.gz.tbi"), emit: annotated

    script:
    """
    set -euo pipefail

    output_vcf="${vcf.simpleName}_fastspliceai.vcf.gz"
    bcftools annotate -a "${cache_vcf}" -c INFO/SpliceAI \\
        -Oz -o "\${output_vcf}" "${vcf}"
    tabix -f -p vcf "\${output_vcf}"
    """
}
