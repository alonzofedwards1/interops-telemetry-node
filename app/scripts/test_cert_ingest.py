from app.transport.certificate_provider import OpenHIMApiCertificateProvider
from app.transport.store import TransportEventStore, EndpointInput

provider = OpenHIMApiCertificateProvider(
    base_url="https://localhost:8080",
    username="root@openhim.org",
    password="Maverick2016!",
    verify_tls=False,
)

cert = provider.get_server_cert()

print("Fingerprint:", cert.fingerprint_sha1)
print("Subject:", cert.subject_cn)
print("Valid From:", cert.not_before)
print("Valid To:", cert.not_after)

store = TransportEventStore()

endpoint_id = store.upsert_endpoint(
    EndpointInput(
        name="openhim-core",
        host="localhost",
        port=8080,
        scheme="https",
        service_type="openhim",
    )
)

cert_id = store.upsert_certificate(cert)

store.insert_endpoint_cert_observation(
    endpoint_id=endpoint_id,
    cert_id=cert_id,
    source="openhim_api",
)

print("Endpoint ID:", endpoint_id)
print("Cert ID:", cert_id)