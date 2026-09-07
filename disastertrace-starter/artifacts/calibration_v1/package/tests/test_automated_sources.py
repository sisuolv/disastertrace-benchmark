"""Source contract tests; edited fixtures are synthetic parser probes, not records."""

import hashlib
import json

import pytest

from disastertrace.automated.sources import parse_nhc, profile_cyportqa

# Verbatim header and current summary from NHC Ida public advisory 10, 2021-08-28.
# The omitted warning/discussion sections are outside this parser's field contract.
IDA_010_SUMMARY = """
ZCZC MIATCPAT4 ALL
TTAA00 KNHC DDHHMM
 
BULLETIN
Hurricane Ida Advisory Number  10
NWS National Hurricane Center Miami FL       AL092021
400 PM CDT Sat Aug 28 2021
 
...IDA RAPIDLY STRENGTHENING OVER THE GULF OF MEXICO...
...LIFE-THREATENING STORM SURGE, POTENTIALLY CATASTROPHIC WIND 
DAMAGE, AND FLOODING RAINFALL EXPECTED TO IMPACT THE NORTHERN GULF 
COAST BEGINNING SUNDAY...
 
 
SUMMARY OF 400 PM CDT...2100 UTC...INFORMATION
----------------------------------------------
LOCATION...26.2N 87.0W
ABOUT 240 MI...385 KM SSE OF THE MOUTH OF THE MISSISSIPPI RIVER
ABOUT 325 MI...525 KM SE OF HOUMA LOUISIANA
MAXIMUM SUSTAINED WINDS...105 MPH...165 KM/H
PRESENT MOVEMENT...NW OR 320 DEGREES AT 16 MPH...26 KM/H
MINIMUM CENTRAL PRESSURE...976 MB...28.82 INCHES
 
 
"""
NHC_URL = "https://www.nhc.noaa.gov/archive/2021/al09/al092021.public.010.shtml"


def admit(text=IDA_010_SUMMARY, **overrides):
    kwargs = {
        "source_id": "nhc-al092021-public-010",
        "source_url": NHC_URL,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    kwargs.update(overrides)
    return parse_nhc(text, **kwargs)


def reject(text, code, **overrides):
    result = admit(text, **overrides)
    assert not result["admitted"]
    assert result["record"] is None
    assert result["rejection_reasons"][0]["code"] == code


def test_actual_ida_summary_known_values_and_line_locators():
    result = admit()
    assert result["admitted"], result
    record = result["record"]
    assert record["storm_id"] == "AL092021"
    assert record["storm_name"] == "Ida"
    assert record["advisory_id"] == "AL092021:public:10"
    assert record["issued_at"] == "2021-08-28T21:00:00+00:00"
    assert record["fields"] == {
        "maximum_wind_mph": 105,
        "latitude_deg": 26.2,
        "longitude_deg": -87.0,
        "movement_direction": "NW",
        "movement_degrees": 320,
        "movement_speed_mph": 16,
        "minimum_pressure_mb": 976,
    }
    assert record["raw_text"] == IDA_010_SUMMARY
    assert record["provenance"]["source_origin"] == "official_record"
    assert record["provenance"]["gold_origin"] == "derived_from_source"
    assert record["provenance"]["availability_proven"] is False
    assert "available_at" not in record
    assert record["field_evidence"]["maximum_wind_mph"]["line_start"] == 21
    for entries in record["field_evidence"].values():
        for entry in entries if isinstance(entries, list) else [entries]:
            assert entry["line_start"] == entry["line_end"]
            assert IDA_010_SUMMARY.splitlines()[entry["line_start"] - 1] == entry["text"]


def test_utc_date_rolls_forward_from_dated_local_header():
    text = IDA_010_SUMMARY.replace("400 PM CDT", "1000 PM CDT").replace("2100 UTC", "0300 UTC")
    assert admit(text)["record"]["issued_at"] == "2021-08-29T03:00:00+00:00"


def test_direct_utc_date_and_summary_are_supported():
    text = IDA_010_SUMMARY.replace("400 PM CDT Sat", "2100 UTC Sat")
    text = text.replace("400 PM CDT...2100 UTC", "2100 UTC")
    assert admit(text)["record"]["issued_at"] == "2021-08-28T21:00:00+00:00"


@pytest.mark.parametrize(
    "before,after,code",
    [
        ("...2100 UTC", "", "UTC_MISSING"),
        ("...2100 UTC", "...2200 UTC", "ISSUED_SUMMARY_MISMATCH"),
        ("...2100 UTC", "...2460 UTC", "TIME_INVALID"),
        ("...2100 UTC", "...2100 UTC...2100 UTC", "SUMMARY_FORMAT_UNSUPPORTED"),
        ("400 PM CDT Sat", "500 PM CDT Sat", "ISSUED_SUMMARY_MISMATCH"),
        ("400 PM CDT", "460 PM CDT", "TIME_INVALID"),
        ("400 PM CDT", "400 PM XYZ", "TIMEZONE_UNSUPPORTED"),
        ("Sat Aug 28", "Sun Aug 28", "DATE_WEEKDAY_MISMATCH"),
        ("Sat Aug 28", "Sat Feb 30", "DATE_INVALID"),
        ("Sat Aug 28", "Sat XYZ 28", "DATE_INVALID"),
        ("Sat Aug 28 2021", "Sat Aug 28", "TIME_FORMAT_UNSUPPORTED"),
        ("105 MPH...165 KM/H", "105 KT...165 KM/H", "FIELD_FORMAT_OR_UNIT_UNSUPPORTED"),
        ("105 MPH...165 KM/H", "105 MPH...200 KM/H", "UNIT_VALUE_MISMATCH"),
        ("105 MPH...165 KM/H", "105 MPH...165", "FIELD_FORMAT_OR_UNIT_UNSUPPORTED"),
        ("16 MPH...26 KM/H", "16 MPH...99 KM/H", "UNIT_VALUE_MISMATCH"),
        ("NW OR 320", "SE OR 320", "DIRECTION_MISMATCH"),
        ("NW OR 320", "NW OR 400", "VALUE_OUT_OF_RANGE"),
        ("28.82 INCHES", "29.99 INCHES", "UNIT_VALUE_MISMATCH"),
        ("26.2N", "96.2N", "VALUE_OUT_OF_RANGE"),
        ("87.0W", "187.0W", "VALUE_OUT_OF_RANGE"),
        ("AL092021", "AL102021", "IDENTITY_MISMATCH"),
        ("Advisory Number  10", "Advisory Number  11", "IDENTITY_MISMATCH"),
    ],
)
def test_ambiguous_or_incompatible_records_are_quarantined(before, after, code):
    reject(IDA_010_SUMMARY.replace(before, after), code)


def test_missing_and_duplicate_summary_rejected():
    reject(IDA_010_SUMMARY.replace("SUMMARY OF", "SUMMARY AT"), "MISSING_FIELD")
    reject(IDA_010_SUMMARY + IDA_010_SUMMARY, "AMBIGUOUS_FIELD")


def test_missing_and_duplicate_required_field_rejected():
    line = "MAXIMUM SUSTAINED WINDS...105 MPH...165 KM/H\n"
    reject(IDA_010_SUMMARY.replace(line, ""), "MISSING_FIELD")
    reject(IDA_010_SUMMARY.replace(line, line + line), "AMBIGUOUS_FIELD")
    conflict = "MAXIMUM SUSTAINED WINDS...85 MPH...140 KM/H\n"
    reject(IDA_010_SUMMARY.replace(line, line + conflict), "AMBIGUOUS_FIELD")


def test_duplicate_or_missing_issue_date_rejected():
    date = "400 PM CDT Sat Aug 28 2021\n"
    reject(IDA_010_SUMMARY.replace(date, date + date), "AMBIGUOUS_FIELD")
    reject(IDA_010_SUMMARY.replace(date, ""), "MISSING_FIELD")


def test_duplicate_utc_in_direct_utc_summary_rejected():
    text = IDA_010_SUMMARY.replace("400 PM CDT", "2100 UTC")
    reject(text, "AMBIGUOUS_UTC")


def test_only_current_summary_is_parsed_and_source_hash_is_enforced():
    text = IDA_010_SUMMARY + "DISCUSSION AND OUTLOOK\nMaximum winds may reach 150 mph.\n"
    result = admit(text)
    assert result["record"]["fields"]["maximum_wind_mph"] == 105
    reject(
        text,
        "SOURCE_HASH_MISMATCH",
        source_sha256=hashlib.sha256(IDA_010_SUMMARY.encode()).hexdigest(),
    )
    reject(text, "SOURCE_HASH_MISMATCH", source_sha256="")


def test_warning_summary_is_not_another_current_information_summary():
    text = IDA_010_SUMMARY + (
        "WATCHES AND WARNINGS\n--------------------\n"
        "SUMMARY OF WATCHES AND WARNINGS IN EFFECT:\n"
        "A Hurricane Warning is in effect for...\n"
    )
    result = admit(text)
    assert result["admitted"], result
    assert result["record"]["fields"]["maximum_wind_mph"] == 105


def test_locators_preserve_crlf_and_hash_does_not_silently_normalize():
    text = IDA_010_SUMMARY.replace("\n", "\r\n")
    result = admit(text)
    assert result["admitted"]
    assert result["record"]["raw_text"] == text
    assert result["record"]["field_evidence"]["maximum_wind_mph"]["line_start"] == 21
    reject(
        text,
        "SOURCE_HASH_MISMATCH",
        source_sha256=hashlib.sha256(IDA_010_SUMMARY.encode()).hexdigest(),
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/archive/2021/al09/al092021.public.010.shtml",
        "https://www.nhc.noaa.gov.evil.invalid/archive/2021/al09/al092021.public.010.shtml",
        NHC_URL + "?version=011",
        "http://www.nhc.noaa.gov/archive/2021/al09/al092021.public.010.shtml",
    ],
)
def test_official_url_contract(url):
    reject(IDA_010_SUMMARY, "SOURCE_URL_UNSUPPORTED", source_url=url)


def test_url_record_identity_is_checked():
    reject(IDA_010_SUMMARY, "IDENTITY_MISMATCH", source_url=NHC_URL.replace(".010.", ".011."))


def test_profile_known_exclusions_are_contract_based_and_not_model_selection(tmp_path):
    path = tmp_path / "templates.json"
    templates = [
        {
            "question_type": [f"Q{number}", "S1", "MC"],
            "modalities": ["text_advisory"],
            "answer": "{answer}",
        }
        for number in (16, 17, 18, 28, 49)
    ]
    templates += [
        {
            "question_type": ["Q1", "TF"],
            "modalities": ["Graphic_Uncertainty_cone"],
            "answer": "{answer}",
        },
        {"question_type": ["Q11", "NU"], "modalities": ["Table_wind"], "answer": "{answer}"},
    ]
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(templates).encode())
    profile = profile_cyportqa(path)
    assert profile["scope"] == "template_declarations_only"
    assert profile["selection_basis"] == "frozen_source_and_task_contract_before_model_results"
    assert profile["template_count"] == 7
    assert profile["modality_counts"]["text_advisory"] == 5
    assert profile["answer_kind_counts"] == {"MC": 5, "NU": 1, "TF": 1}
    rows = {row["template_id"]: row for row in profile["templates"]}
    for template_id, code in (
        ("Q16", "CONTEXT_ANSWER_SHORTCUT"),
        ("Q17", "LANDFALL_IMPACT_SEMANTICS"),
        ("Q18", "LABEL_OPTION_MISMATCH"),
        ("Q28", "ONSET_LANDFALL_SEMANTICS"),
    ):
        assert rows[template_id]["role"] == "excluded_from_new_core"
        assert rows[template_id]["reason_codes"][0]["code"] == code
    assert rows["Q49"]["role"] == "text_candidate_requires_source_validation"
    assert rows["Q1"]["role"] == "visual_evidence_required"
    assert rows["Q11"]["role"] == "source_format_verification_required"


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        '[{"question_type":["Q1"],"modalities":["text_advisory"],"answer":1,"answer":2}]',
        '[{"question_type":["Q1"],"modalities":["text_advisory"]}]',
        '[{"question_type":["Q1", "Q2"],"modalities":["text_advisory"],"answer":1}]',
        '[{"question_type":["Q1"],"modalities":[],"answer":1}]',
    ],
)
def test_profile_does_not_silently_accept_malformed_templates(tmp_path, content):
    path = tmp_path / "templates.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        profile_cyportqa(path)
