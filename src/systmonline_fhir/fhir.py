from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from .parser import RecordEvent

UK_CORE_CANONICAL = "https://fhir.hl7.org.uk/StructureDefinition"
UK_CORE_PACKAGE = "fhir.r4.ukcore.stu2#2.0.1"


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

UK_CORE_PROFILES = {
    "Patient": f"{UK_CORE_CANONICAL}/UKCore-Patient",
    "Condition": f"{UK_CORE_CANONICAL}/UKCore-Condition",
    "MedicationStatement": f"{UK_CORE_CANONICAL}/UKCore-MedicationStatement",
    "AllergyIntolerance": f"{UK_CORE_CANONICAL}/UKCore-AllergyIntolerance",
    "Immunization": f"{UK_CORE_CANONICAL}/UKCore-Immunization",
    "Observation": f"{UK_CORE_CANONICAL}/UKCore-Observation",
}


def _resource(event: RecordEvent, patient_id: str) -> dict:
    resource_type = RESOURCE_TYPES.get(event.entry_type.casefold(), "Basic")
    stable = f"{event.date}|{event.entry_type}|{event.text}|{event.source_sha256}"
    identifier = str(uuid5(NAMESPACE_URL, stable))
    resource: dict = {
        "resourceType": resource_type,
        "id": identifier,
        "meta": {
            "source": f"urn:sha256:{event.source_sha256}",
            **({"profile": [UK_CORE_PROFILES[resource_type]]} if resource_type in UK_CORE_PROFILES else {}),
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "extension": [{
            "url": "https://devnull.co.uk/fhir/StructureDefinition/source-entry-type",
            "valueString": event.entry_type,
        }],
    }
    if resource_type == "Condition":
        resource.update({"code": {"text": event.text}})
        if event.date != "unknown":
            resource["recordedDate"] = event.date
    elif resource_type == "MedicationStatement":
        resource.update({"status": "unknown", "medicationCodeableConcept": {"text": event.text}})
        if event.date != "unknown":
            resource["dateAsserted"] = event.date
    elif resource_type == "AllergyIntolerance":
        resource.update({"code": {"text": event.text}, "patient": resource.pop("subject")})
        if event.date != "unknown":
            resource["recordedDate"] = event.date
    elif resource_type == "Immunization":
        resource.update({"status": "completed", "vaccineCode": {"text": event.text}, "patient": resource.pop("subject")})
        if event.date != "unknown":
            resource["occurrenceDateTime"] = event.date
        else:
            resource["occurrenceString"] = "Date not supplied by source view"
    elif resource_type == "Observation":
        resource.update({"status": "final", "code": {"text": event.entry_type}, "valueString": event.text})
        if event.date != "unknown":
            resource["effectiveDateTime"] = event.date
    elif resource_type == "DocumentReference":
        resource.update({"status": "current", "date": event.date, "description": event.text, "content": []})
    else:
        resource.update({"created": event.date, "code": {"text": event.entry_type}, "extension": resource["extension"] + [{"url": "https://devnull.co.uk/fhir/StructureDefinition/source-text", "valueString": event.text}]})
    return resource


def bundle(events: list[RecordEvent], patient_id: str = "personal-record") -> dict:
    patient = {"resourceType": "Patient", "id": patient_id, "meta": {"profile": [UK_CORE_PROFILES["Patient"]]}}
    resources = [patient, *(_resource(event, patient_id) for event in events)]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"fullUrl": f"https://healthdata.devnull.co.uk/fhir/{item['resourceType']}/{item['id']}", "resource": item} for item in resources],
    }
