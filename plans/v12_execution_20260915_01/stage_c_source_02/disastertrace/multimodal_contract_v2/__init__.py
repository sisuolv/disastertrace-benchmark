"""Explicit output-shape instructions; frozen MM-3 v1 requests stay unchanged."""

from copy import deepcopy


def output_schema():
    reference = {"anyOf": [{"type": "string", "minLength": 1, "maxLength": 80}, {"type": "null"}]}
    fields = {
        "relation": {
            "type": "string",
            "enum": ["inside", "outside", "boundary_ambiguous", "unknown"],
        },
        "watched": {"type": ["boolean", "null"]},
        "inspection_required": {"type": ["boolean", "null"]},
        "map_source": deepcopy(reference),
        "map_locator": deepcopy(reference),
        "rule_source": deepcopy(reference),
        "rule_locator": deepcopy(reference),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["state"],
        "additionalProperties": False,
        "properties": {
            "state": {
                "type": "object",
                "maxProperties": 64,
                "propertyNames": {"type": "string", "minLength": 1, "maxLength": 32},
                "additionalProperties": {
                    "type": "object",
                    "required": list(fields),
                    "additionalProperties": False,
                    "properties": fields,
                },
            }
        },
    }


def explicit_contract(request):
    result = deepcopy(request)
    result["output_contract"]["format_version"] = "explicit_site_mapping_v2"
    result["output_contract"]["root"] = (
        "Submit only one JSON object with the single key state. "
        "The value of state MUST be an object, keyed by each currently revealed site_id string. "
        "For each site key, its value MUST be an object containing exactly the seven site_fields. "
        "Do not use an array for state. Do not put a site_id field inside a site record. "
        "Include all currently revealed sites and no other sites. All JSON keys must be unique."
    )
    result["output_contract"]["json_schema"] = output_schema()
    return result
