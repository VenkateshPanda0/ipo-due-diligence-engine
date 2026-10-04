# Real-document extraction benchmark — results

Generated 2026-10-04T20:27:22+00:00 · split `all` · OCR on.
Answer keys were prepared by an AI assistant from poppler text and have **not** been verified by a human.

| Metric | All | Development | Holdout |
|---|---|---|---|
| documents | 8 | 5 | 3 |
| scored_fields | 84 | 48 | 36 |
| correct | 69 | 48 | 21 |
| wrong | 6 | 0 | 6 |
| missing | 9 | 0 | 9 |
| flagged | 23 | 10 | 13 |
| false_high | 3 | 0 | 3 |
| precision | 0.92 | 1.0 | 0.7778 |
| recall | 0.8214 | 1.0 | 0.5833 |
| missing_rate | 0.1071 | 0.0 | 0.25 |
| false_high_rate | 0.0357 | 0.0 | 0.0833 |
| correct_abstentions | 6 | 6 | 0 |
| abstention_cases | 9 | 9 | 0 |
| route_correct | 8 | 5 | 3 |

## By field (all documents)

| Field | Expected | Correct | Wrong | Missing | False-high |
|---|---|---|---|---|---|
| ebitda | 3 | 3 | 0 | 0 | 0 |
| monetary_assets | 18 | 15 | 0 | 3 | 0 |
| net_tangible_assets | 18 | 15 | 0 | 3 | 0 |
| net_worth | 21 | 18 | 3 | 0 | 3 |
| operating_profit | 18 | 15 | 0 | 3 | 0 |
| pat | 3 | 0 | 3 | 0 | 0 |
| revenue | 3 | 3 | 0 | 0 | 0 |

## By document

| Document | Split | Correct | Wrong | Missing | Flagged | Route | Seconds |
|---|---|---|---|---|---|---|---|
| madhur-iron-and-steel-india-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 47.3 |
| ekkaa-electronics-india-limited-drhp | development | 12/12 | 0 | 0 | 4 | ✓ | 58.5 |
| jsw-one-platforms-limited-drhp | development | 12/12 | 0 | 0 | 6 | ✓ | 71.5 |
| iris-global-services-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 36.3 |
| jagatjit-agri-engineering-limited-drhp | development | 0/0 | 0 | 0 | 0 | ✓ | 62.1 |
| iberia-pharmaceuticals-india-limited-drhp | holdout | 12/12 | 0 | 0 | 0 | ✓ | 48.4 |
| vardaan-biotech-limited-drhp | holdout | 0/12 | 3 | 9 | 6 | ✓ | 45.4 |
| anchor-offshore-services-limited-drhp | holdout | 9/12 | 3 | 0 | 7 | ✓ | 54.2 |

## Field-level detail

### madhur-iron-and-steel-india-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 329.4697 | 329.4697 | extracted_high_confidence | 502 | correct |
| [FY2025].net_tangible_assets | 235.1886 | 235.1886 | extracted_high_confidence | 502 | correct |
| [FY2024].net_tangible_assets | 126.5915 | 126.5915 | extracted_high_confidence | 502 | correct |
| [FY2026].monetary_assets | 0.2219 | 0.2219 | extracted_high_confidence | 502 | correct |
| [FY2025].monetary_assets | 0.6992 | 0.6992 | extracted_high_confidence | 502 | correct |
| [FY2024].monetary_assets | 0.0027 | 0.0027 | extracted_high_confidence | 502 | correct |
| [FY2026].operating_profit | 49.9128 | 49.9128 | extracted_high_confidence | 502 | correct |
| [FY2025].operating_profit | 35.9218 | 35.9218 | extracted_high_confidence | 502 | correct |
| [FY2024].operating_profit | 23.8650 | 23.8650 | extracted_high_confidence | 502 | correct |
| [FY2026].net_worth | 117.8973 | 117.8973 | extracted_high_confidence | 502 | correct |
| [FY2025].net_worth | 93.9947 | 93.9947 | extracted_high_confidence | 502 | correct |
| [FY2024].net_worth | 42.7712 | 42.7712 | extracted_high_confidence | 502 | correct |

### ekkaa-electronics-india-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 253.249 | 253.249 | extracted_high_confidence | 453 | correct |
| [FY2025].net_tangible_assets | 41.980 | 41.980 | extracted_needs_verification | 453 | correct |
| [FY2024].net_tangible_assets | 16.711 | 16.711 | extracted_needs_verification | 453 | correct |
| [FY2026].monetary_assets | 2.340 | 2.340 | extracted_high_confidence | 453 | correct |
| [FY2025].monetary_assets | 0.224 | 0.224 | extracted_needs_verification | 453 | correct |
| [FY2024].monetary_assets | 0.292 | 0.292 | extracted_needs_verification | 453 | correct |
| [FY2026].operating_profit | 100.869 | 100.869 | extracted_high_confidence | 453 | correct |
| [FY2025].operating_profit | 46.656 | 46.656 | extracted_high_confidence | 453 | correct |
| [FY2024].operating_profit | -1.196 | -1.196 | extracted_high_confidence | 453 | correct |
| [FY2026].net_worth | 251.525 | 251.525 | extracted_high_confidence | 453 | correct |
| [FY2025].net_worth | 38.221 | 38.221 | extracted_high_confidence | 453 | correct |
| [FY2024].net_worth | 14.669 | 14.669 | extracted_high_confidence | 453 | correct |

### jsw-one-platforms-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 558.574 | 558.574 | extracted_needs_verification | 457 | correct |
| [FY2025].net_tangible_assets | 76.918 | 76.918 | extracted_needs_verification | 457 | correct |
| [FY2024].net_tangible_assets | 234.723 | 234.723 | extracted_needs_verification | 457 | correct |
| [FY2026].monetary_assets | 418.183 | 418.183 | extracted_needs_verification | 457 | correct |
| [FY2025].monetary_assets | 101.837 | 101.837 | extracted_needs_verification | 457 | correct |
| [FY2024].monetary_assets | 189.045 | 189.045 | extracted_needs_verification | 457 | correct |
| [FY2026].operating_profit | -121.241 | -121.241 | extracted_high_confidence | 457 | correct |
| [FY2025].operating_profit | -217.572 | -217.572 | extracted_high_confidence | 457 | correct |
| [FY2024].operating_profit | -241.188 | -241.188 | extracted_high_confidence | 457 | correct |
| [FY2026].net_worth | 556.488 | 556.488 | extracted_high_confidence | 457 | correct |
| [FY2025].net_worth | 75.795 | 75.795 | extracted_high_confidence | 457 | correct |
| [FY2024].net_worth | 233.804 | 233.804 | extracted_high_confidence | 457 | correct |

### iris-global-services-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 296.278 | 296.278 | extracted_high_confidence | 353 | correct |
| [FY2025].net_tangible_assets | 220.099 | 220.099 | extracted_high_confidence | 353 | correct |
| [FY2024].net_tangible_assets | 158.115 | 158.115 | extracted_high_confidence | 353 | correct |
| [FY2026].monetary_assets | 6.328 | 6.328 | extracted_high_confidence | 353 | correct |
| [FY2025].monetary_assets | 0.097 | 0.097 | extracted_high_confidence | 353 | correct |
| [FY2024].monetary_assets | 0.226 | 0.226 | extracted_high_confidence | 353 | correct |
| [FY2026].operating_profit | 126.734 | 126.734 | extracted_high_confidence | 353 | correct |
| [FY2025].operating_profit | 92.775 | 92.775 | extracted_high_confidence | 353 | correct |
| [FY2024].operating_profit | 75.584 | 75.584 | extracted_high_confidence | 353 | correct |
| [FY2026].net_worth | 298.655 | 298.655 | extracted_high_confidence | 353 | correct |
| [FY2025].net_worth | 221.569 | 221.569 | extracted_high_confidence | 353 | correct |
| [FY2024].net_worth | 159.348 | 159.348 | extracted_high_confidence | 353 | correct |

### jagatjit-agri-engineering-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2025].net_tangible_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2024].net_tangible_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2026].monetary_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2025].monetary_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2024].monetary_assets | None | None | extracted_needs_verification | None | correct_abstention |
| [FY2026].net_worth | None | 70.929 | extracted_high_confidence | 91 | wrong_normalisation |
| [FY2025].net_worth | None | 7.078 | extracted_needs_verification | 402 | wrong_normalisation |
| [FY2024].net_worth | None | 0.532 | extracted_needs_verification | 402 | wrong_normalisation |

### iberia-pharmaceuticals-india-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 50.9727 | 50.9727 | extracted_high_confidence | 374 | correct |
| [FY2025].net_tangible_assets | 40.0310 | 40.0310 | extracted_high_confidence | 374 | correct |
| [FY2024].net_tangible_assets | 13.9580 | 13.9580 | extracted_high_confidence | 374 | correct |
| [FY2026].monetary_assets | 7.5996 | 7.5996 | extracted_high_confidence | 374 | correct |
| [FY2025].monetary_assets | 1.0904 | 1.0904 | extracted_high_confidence | 374 | correct |
| [FY2024].monetary_assets | 0.7232 | 0.7232 | extracted_high_confidence | 374 | correct |
| [FY2026].operating_profit | 15.0892 | 15.0892 | extracted_high_confidence | 374 | correct |
| [FY2025].operating_profit | 20.5418 | 20.5418 | extracted_high_confidence | 374 | correct |
| [FY2024].operating_profit | 10.4324 | 10.4324 | extracted_high_confidence | 374 | correct |
| [FY2026].net_worth | 51.6482 | 51.6482 | extracted_high_confidence | 374 | correct |
| [FY2025].net_worth | 39.9518 | 39.9518 | extracted_high_confidence | 374 | correct |
| [FY2024].net_worth | 14.6174 | 14.6174 | extracted_high_confidence | 374 | correct |

### vardaan-biotech-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 99.5475 | None | extracted_needs_verification | None | missing |
| [FY2025].net_tangible_assets | 60.9993 | None | not_found | None | missing |
| [FY2024].net_tangible_assets | 43.3670 | None | extracted_needs_verification | None | missing |
| [FY2026].monetary_assets | 0.3130 | None | extracted_needs_verification | None | missing |
| [FY2025].monetary_assets | 0.5579 | None | not_found | None | missing |
| [FY2024].monetary_assets | 0.3444 | None | extracted_needs_verification | None | missing |
| [FY2026].operating_profit | 28.2059 | None | extracted_needs_verification | None | missing |
| [FY2025].operating_profit | 26.7299 | None | not_found | None | missing |
| [FY2024].operating_profit | 23.7652 | None | extracted_needs_verification | None | missing |
| [FY2026].net_worth | 99.5475 | 99.5475 | extracted_high_confidence | 320 | wrong_page |
| [FY2025].net_worth | 60.9993 | 60.9993 | extracted_high_confidence | 320 | wrong_page |
| [FY2024].net_worth | 43.3671 | 43.3671 | extracted_high_confidence | 320 | wrong_page |

### anchor-offshore-services-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].revenue | 105.827 | 105.827 | conflicting_candidates | 80 | correct |
| [FY2025].revenue | 139.989 | 139.989 | conflicting_candidates | 80 | correct |
| [FY2024].revenue | 117.904 | 117.904 | conflicting_candidates | 80 | correct |
| [FY2026].pat | 8.035 | 8.035 | conflicting_candidates | 283 | wrong_page |
| [FY2025].pat | 12.886 | 12.886 | conflicting_candidates | 283 | wrong_page |
| [FY2024].pat | -6.709 | -6.709 | conflicting_candidates | 283 | wrong_page |
| [FY2026].ebitda | 12.033 | 12.033 | extracted_high_confidence | 142 | correct |
| [FY2025].ebitda | 11.649 | 11.649 | extracted_high_confidence | 142 | correct |
| [FY2024].ebitda | 3.650 | 3.650 | extracted_high_confidence | 142 | correct |
| [FY2026].net_worth | 128.135 | 128.135 | conflicting_candidates | 142 | correct |
| [FY2025].net_worth | 91.336 | 91.336 | extracted_high_confidence | 142 | correct |
| [FY2024].net_worth | 78.595 | 78.595 | extracted_high_confidence | 142 | correct |

