# M01 selector development result

{"passed": true, "registered_days": 12, "complete_days": 12, "registered_opportunities": 864, "registered_request_cap": 288, "HTTP_intents": 275, "source": "actual model capture; program probabilities; end-to-end development only", "confirmation_opened": false, "automatic_retries": 0, "finished_at": "2026-09-16T14:47:25.379081+00:00", "schema_valid": 275, "provider_tokens_known": 1119368, "requests_without_usage": 13, "rows_sha256": "158ad2f98f9298b0ea2c4269820597eb424ca1cbb4833271ae8ed8c4d3ab25ad"}

The model chooses source queries. The frozen program produces probabilities. Invalid responses, HTTP failures, late forecasts and fallback remain in the end-to-end denominator.

This comparison does not validate model-authored weather probabilities, independent confirmation, or another hazard.

| Program reference | Mean Brier gain (positive favors model) | Missing-Y bound |
|---|---:|---|
| F_BASE_ONLY | 4.52854675731627e-05 | [-0.00022416772962765525, 5.321446370083153e-05] |
| B11_BATCH | 0.0002551673514469421 | [0.0001707722367254944, 0.00030431632396222614] |
| B11_COVERAGE | 6.367438949104162e-05 | [4.501319214848142e-05, 0.00012650580509954393] |
| B11_RR_CYCLE | -4.94579679997597e-05 | [-5.127717959631906e-05, 1.656446566921155e-05] |
| B11_RISK_AGE | 0.00018086312118182103 | [0.00017114858345811508, 0.00024520759826947145] |
| B11_FIXED_HASH | -5.603249407174948e-05 | [-6.38277386163177e-05, 1.0231276195038673e-05] |
| B00_COVERAGE | -0.00015483647347628492 | [-0.00020548380213461612, -0.00010004731264352645] |
| B01_COVERAGE | -5.165173953027117e-05 | [-7.940706010805267e-05, 1.460044502385021e-05] |
| B10_COVERAGE | 0.00014191736860213433 | [-7.380285806931542e-06, 0.00016217461256793597] |
