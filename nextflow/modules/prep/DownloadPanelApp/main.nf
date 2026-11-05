process DownloadPanelApp {
    containerOptions '--bind /etc/ssl/certs/ca-bundle.crt:/etc/ssl/certs/ca-bundle.crt'

    input:
        path mane
        val timestamp

    output:
        path "panelapp_${timestamp}.json"

    script:
        """
        set -euo pipefail
        export PYTHONPATH="${projectDir}/src:\$PYTHONPATH"
        export http_proxy=http://proxy-default:3128
        export https_proxy=http://proxy-default:3128
        export HTTPS_CA_FILE=/etc/ssl/certs/ca-bundle.crt
        export SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt

        python -m talos.download_panelapp \
            --output panelapp_${timestamp}.json \
            --mane ${mane}
        """
}
