process AnnotateWithFastSpliceAi {
    cpus 6
    memory 16.GB
    time '8h'

    input:
        tuple val(cohort), path(vcf), path(vcf_index)
        val reference_fasta
        val cache_vcf

    output:
        tuple val(cohort), path("${vcf.simpleName}_fastspliceai.vcf.gz"), path("${vcf.simpleName}_fastspliceai.vcf.gz.tbi")

    script:
    """
    set -euo pipefail
    umask 002

    test -x "${params.fastspliceai_bin}"
    test -f "${reference_fasta}"
    test -f "${reference_fasta}.fai"

    output_vcf="${vcf.simpleName}_fastspliceai.vcf.gz"

    if [[ -z "${cache_vcf}" ]]; then
        "${params.fastspliceai_bin}" \\
            -I "${vcf}" \\
            -O "\${output_vcf}" \\
            -R "${reference_fasta}" \\
            -A grch38 \\
            --output-type z \\
            --write-index=tbi \\
            --overwrite-existing \\
            --device cuda \\
            --threads "${task.cpus}"
        exit 0
    fi

    cache_dir="\$(dirname "${cache_vcf}")"
    mkdir -p "\${cache_dir}"

    # The cache has no genotypes. Its site membership records both positive
    # scores and variants already evaluated without a useful SpliceAI value.
    bcftools view -G -Oz -o cohort_sites.vcf.gz "${vcf}"
    tabix -f -p vcf cohort_sites.vcf.gz

    if [[ -f "${cache_vcf}" ]]; then
        if [[ ! -f "${cache_vcf}.tbi" ]]; then
            tabix -f -p vcf "${cache_vcf}"
        fi
        bcftools isec -C -c none -w 1 -Oz -o cache_misses.vcf.gz \\
            cohort_sites.vcf.gz "${cache_vcf}"
    else
        cp cohort_sites.vcf.gz cache_misses.vcf.gz
    fi
    tabix -f -p vcf cache_misses.vcf.gz

    if [[ "\$(bcftools index -n cache_misses.vcf.gz)" -gt 0 ]]; then
        "${params.fastspliceai_bin}" \\
            -I cache_misses.vcf.gz \\
            -O cache_additions.vcf.gz \\
            -R "${reference_fasta}" \\
            -A grch38 \\
            --output-type z \\
            --write-index=tbi \\
            --overwrite-existing \\
            --device cuda \\
            --threads "${task.cpus}"
        bcftools view -G -Oz -o cache_additions.sites.vcf.gz cache_additions.vcf.gz
        tabix -f -p vcf cache_additions.sites.vcf.gz

        # Scoring occurs outside the lock. The lock only protects the atomic
        # cache merge and allows concurrent runs to safely score overlapping sites.
        (
            flock -x 9
            cache_tmp="\$(mktemp "${cache_vcf}.tmp.XXXXXX")"
            if [[ -f "${cache_vcf}" ]]; then
                bcftools concat -a "${cache_vcf}" cache_additions.sites.vcf.gz -Ou | \\
                    bcftools sort -Ou | \\
                    bcftools norm -d exact -Oz -o "\${cache_tmp}"
            else
                cp cache_additions.sites.vcf.gz "\${cache_tmp}"
            fi
            tabix -f -p vcf "\${cache_tmp}"
            mv -f "\${cache_tmp}" "${cache_vcf}"
            mv -f "\${cache_tmp}.tbi" "${cache_vcf}.tbi"
        ) 9>"${cache_vcf}.lock"
    fi

    if [[ -f "${cache_vcf}" ]]; then
        bcftools annotate -a "${cache_vcf}" -c INFO/SpliceAI \\
            -Oz -o "\${output_vcf}" "${vcf}"
        tabix -f -p vcf "\${output_vcf}"
    else
        cp "${vcf}" "\${output_vcf}"
        cp "${vcf_index}" "\${output_vcf}.tbi"
    fi
    """
}
