process CheckFastSpliceAiCache {
    tag "$cohort"

    input:
    tuple val(cohort), path(vcf), path(vcf_index)
    val cache_vcf

    output:
    tuple val(cohort), path(vcf), path(vcf_index), path("cohort_sites.vcf.gz"), path("cohort_sites.vcf.gz.tbi"), path("cache_misses.vcf.gz"), path("cache_misses.vcf.gz.tbi"), path("cache_status.txt"), emit: checked

    script:
    """
    set -euo pipefail

    bcftools view -G -Oz -o cohort_sites.vcf.gz "${vcf}"
    tabix -f -p vcf cohort_sites.vcf.gz

    if [[ -f "${cache_vcf}" ]]; then
        if [[ ! -f "${cache_vcf}.tbi" ]]; then
            tabix -f -p vcf "${cache_vcf}"
        fi
        bcftools isec -C -c none -w 1 -Oz \\
            -o cache_misses.vcf.gz \\
            cohort_sites.vcf.gz "${cache_vcf}"
    else
        cp cohort_sites.vcf.gz cache_misses.vcf.gz
    fi
    tabix -f -p vcf cache_misses.vcf.gz

    bcftools index -n cache_misses.vcf.gz > cache_status.txt
    """
}
