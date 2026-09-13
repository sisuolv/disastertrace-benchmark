"""Record the installed decoder's actual compatibility, including failure."""

import json
from pathlib import Path

import eccodes


def main():
    root = Path(__file__).resolve().parent
    result = {"decoder": "eccodes", "version": eccodes.__version__, "data_fields_decoded": False}
    with (root / "raw/lmp_20260913_t0030z.bufr").open("rb") as source:
        handle = eccodes.codes_bufr_new_from_file(source)
        try:
            for name in ("edition", "bufrHeaderCentre", "masterTablesVersionNumber", "localTablesVersionNumber", "numberOfSubsets"):
                result[name] = eccodes.codes_get(handle, name)
            result["unexpandedDescriptors"] = eccodes.codes_get_array(handle, "unexpandedDescriptors").tolist()
            try:
                eccodes.codes_set(handle, "unpack", 1)
                result["data_fields_decoded"] = True
            except eccodes.CodesInternalError as error:
                result["decode_error"] = str(error)
        finally:
            eccodes.codes_release(handle)
    (root / "BUFR_DECODER_RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
