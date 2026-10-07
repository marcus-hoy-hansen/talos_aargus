process IndexVcf {
    cpus 1
    memory 1.GB

    input:
        tuple val(cohort), path(vcf)

    output:
        tuple val(cohort), path(vcf), path("${vcf}.tbi")

    script:
    """
    set -euo pipefail
    tabix -f -p vcf "${vcf}"
    """
}
