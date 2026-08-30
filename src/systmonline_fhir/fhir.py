from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from .parser import RecordEvent


RESOURCE_TYPES = {
    "problem": "Condition",
    "medication": "MedicationStatement",
    "drug sensitivity": "AllergyIntolerance",
    "vaccination": "Immunization",
    "test result": "Observation",
    "blood pressure": "Observation",
    "letter": "DocumentReference",
    "attachment": "DocumentReference",
}


def _resource(event: RecordEvent, patient_id: str) -> dict:
    resource_type = RESOURCE_TYPES.get(event.entry_type.casefold(), "Basic")
    stable = "|".join((event.date, event.entry_type, event.text, event.source_sha256))
    identifier = str(uuid5(NAMESPACE_URL, stable))
    resource: dict = {
        "resourceType": resource_type,
        "id": identifier,
        "meta": {"source": f"urn:sha256:{event.source_sha256}"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "extension": [{
            "url": "https://devnull.co.uk/fhir/StructureDefinition/source-entry-type",
            "valueString": event.entry_type,
        }],
    }
    if resource_type == "Condition":
        resource.update({"recordedDate": event.date, "code": {"text": event.text}})
    elif resource_type == "MedicationStatement":
        resource.update({"status": "unknown", "dateAsserted": event.date, "medicationCodeableConcept": {"text": event.text}})
    elif resource_type == "AllergyIntolerance":
        resource.update({"recordedDate": event.date, "code": {"text": event.text}})
    elif resource_type == "Immunization":
        resource.update({"status": "completed", "occurrenceDateTime": event.date, "vaccineCode": {"text": event.text}, "patient": resource.pop("subject")})
    elif resource_type == "Observation":
        resource.update({"status": "final", "effectiveDateTime": event.date, "code": {"text": event.entry_type}, "valueString": event.text})
    elif resource_type == "DocumentReference":
        resource.update({"status": "current", "date": event.date, "description": event.text, "content": []})
    else:
        resource.update({"created": event.date, "code": {"text": event.entry_type}, "extension": resource["extension"] + [{"url": "https://devnull.co.uk/fhir/StructureDefinition/source-text", "valueString": event.text}]})
    return resource


def bundle(events: list[RecordEvent], patient_id: str = "personal-record") -> dict:
    patient = {"resourceType": "Patient", "id": patient_id}
    resources = [patient, *(_resource(event, patient_id) for event in events)]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"fullUrl": f"urn:uuid:{item['id']}", "resource": item} for item in resources],
    }
