# Real-document extraction benchmark — results

Generated 2026-10-04T23:02:56+00:00 · split `all` · OCR on.
Answer keys were prepared by an AI assistant from poppler text and have **not** been verified by a human.

| Metric | All | Development | Holdout |
|---|---|---|---|
| documents | 13 | 8 | 5 |
| scored_fields | 144 | 84 | 60 |
| correct | 138 | 81 | 57 |
| wrong | 6 | 3 | 3 |
| missing | 0 | 0 | 0 |
| flagged | 16 | 14 | 2 |
| false_high | 6 | 3 | 3 |
| precision | 0.9583 | 0.9643 | 0.95 |
| recall | 0.9583 | 0.9643 | 0.95 |
| missing_rate | 0.0 | 0.0 | 0.0 |
| false_high_rate | 0.0417 | 0.0357 | 0.05 |
| correct_abstentions | 6 | 6 | 0 |
| abstention_cases | 9 | 9 | 0 |
| route_correct | 13 | 8 | 5 |

## By field (all documents)

| Field | Expected | Correct | Wrong | Missing | False-high |
|---|---|---|---|---|---|
| ebitda | 3 | 3 | 0 | 0 | 0 |
| monetary_assets | 33 | 33 | 0 | 0 | 0 |
| net_tangible_assets | 33 | 33 | 0 | 0 | 0 |
| net_worth | 36 | 33 | 3 | 0 | 3 |
| operating_profit | 33 | 33 | 0 | 0 | 0 |
| pat | 3 | 0 | 3 | 0 | 3 |
| revenue | 3 | 3 | 0 | 0 | 0 |

## By document

| Document | Split | Correct | Wrong | Missing | Flagged | Route | Seconds |
|---|---|---|---|---|---|---|---|
| madhur-iron-and-steel-india-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 25.8 |
| ekkaa-electronics-india-limited-drhp | development | 12/12 | 0 | 0 | 4 | ✓ | 30.1 |
| jsw-one-platforms-limited-drhp | development | 12/12 | 0 | 0 | 6 | ✓ | 37.9 |
| iris-global-services-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 17.0 |
| jagatjit-agri-engineering-limited-drhp | development | 0/0 | 0 | 0 | 0 | ✓ | 36.5 |
| iberia-pharmaceuticals-india-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 25.7 |
| vardaan-biotech-limited-drhp | development | 12/12 | 0 | 0 | 0 | ✓ | 24.2 |
| anchor-offshore-services-limited-drhp | development | 9/12 | 3 | 0 | 4 | ✓ | 32.4 |
| royal-chain-limited-drhp | holdout | 9/12 | 3 | 0 | 0 | ✓ | 29.1 |
| hi-tech-flow-solutions-limited-drhp | holdout | 12/12 | 0 | 0 | 0 | ✓ | 27.4 |
| m-k-c-agro-fresh-limited-drhp | holdout | 12/12 | 0 | 0 | 0 | ✓ | 24.8 |
| maharashtra-oil-extractions-limited-drhp | holdout | 12/12 | 0 | 0 | 2 | ✓ | 36.4 |
| ultravibrant-integrated-energy-limited-drhp | holdout | 12/12 | 0 | 0 | 0 | ✓ | 42.5 |

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
| [FY2026].net_tangible_assets | 99.5475 | 99.5475 | extracted_high_confidence | 354 | correct |
| [FY2025].net_tangible_assets | 60.9993 | 60.9993 | extracted_high_confidence | 354 | correct |
| [FY2024].net_tangible_assets | 43.3670 | 43.3670 | extracted_high_confidence | 354 | correct |
| [FY2026].monetary_assets | 0.3130 | 0.3130 | extracted_high_confidence | 354 | correct |
| [FY2025].monetary_assets | 0.5579 | 0.5579 | extracted_high_confidence | 354 | correct |
| [FY2024].monetary_assets | 0.3444 | 0.3444 | extracted_high_confidence | 354 | correct |
| [FY2026].operating_profit | 28.2059 | 28.2059 | extracted_high_confidence | 354 | correct |
| [FY2025].operating_profit | 26.7299 | 26.7299 | extracted_high_confidence | 354 | correct |
| [FY2024].operating_profit | 23.7652 | 23.7652 | extracted_high_confidence | 354 | correct |
| [FY2026].net_worth | 99.5475 | 99.5475 | extracted_high_confidence | 354 | correct |
| [FY2025].net_worth | 60.9993 | 60.9993 | extracted_high_confidence | 354 | correct |
| [FY2024].net_worth | 43.3671 | 43.3671 | extracted_high_confidence | 354 | correct |

### anchor-offshore-services-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].revenue | 105.827 | 105.827 | conflicting_candidates | 80 | correct |
| [FY2025].revenue | 139.989 | 139.989 | conflicting_candidates | 80 | correct |
| [FY2024].revenue | 117.904 | 117.904 | conflicting_candidates | 80 | correct |
| [FY2026].pat | 8.035 | 8.035 | extracted_high_confidence | 283 | wrong_page |
| [FY2025].pat | 12.886 | 12.886 | extracted_high_confidence | 283 | wrong_page |
| [FY2024].pat | -6.709 | -6.709 | extracted_high_confidence | 283 | wrong_page |
| [FY2026].ebitda | 12.033 | 12.033 | extracted_high_confidence | 142 | correct |
| [FY2025].ebitda | 11.649 | 11.649 | extracted_high_confidence | 142 | correct |
| [FY2024].ebitda | 3.650 | 3.650 | extracted_high_confidence | 142 | correct |
| [FY2026].net_worth | 128.135 | 128.135 | conflicting_candidates | 142 | correct |
| [FY2025].net_worth | 91.336 | 91.336 | extracted_high_confidence | 142 | correct |
| [FY2024].net_worth | 78.595 | 78.595 | extracted_high_confidence | 142 | correct |

### royal-chain-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 464.323 | 464.323 | extracted_high_confidence | 379 | correct |
| [FY2025].net_tangible_assets | 185.670 | 185.670 | extracted_high_confidence | 379 | correct |
| [FY2024].net_tangible_assets | 123.457 | 123.457 | extracted_high_confidence | 379 | correct |
| [FY2026].monetary_assets | 40.725 | 40.725 | extracted_high_confidence | 379 | correct |
| [FY2025].monetary_assets | 4.271 | 4.271 | extracted_high_confidence | 379 | correct |
| [FY2024].monetary_assets | 6.844 | 6.844 | extracted_high_confidence | 379 | correct |
| [FY2026].operating_profit | 264.227 | 264.227 | extracted_high_confidence | 379 | correct |
| [FY2025].operating_profit | 115.613 | 115.613 | extracted_high_confidence | 379 | correct |
| [FY2024].operating_profit | 57.306 | 57.306 | extracted_high_confidence | 379 | correct |
| [FY2026].net_worth | 465.751 | 465.751 | extracted_high_confidence | 338 | wrong_page |
| [FY2025].net_worth | 184.220 | 184.220 | extracted_high_confidence | 338 | wrong_page |
| [FY2024].net_worth | 120.984 | 120.984 | extracted_high_confidence | 338 | wrong_page |

### hi-tech-flow-solutions-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 130.236 | 130.236 | extracted_high_confidence | 455 | correct |
| [FY2025].net_tangible_assets | 92.942 | 92.942 | extracted_high_confidence | 455 | correct |
| [FY2024].net_tangible_assets | 68.019 | 68.019 | extracted_high_confidence | 455 | correct |
| [FY2026].monetary_assets | 0.065 | 0.065 | extracted_high_confidence | 455 | correct |
| [FY2025].monetary_assets | 10.521 | 10.521 | extracted_high_confidence | 455 | correct |
| [FY2024].monetary_assets | 36.813 | 36.813 | extracted_high_confidence | 455 | correct |
| [FY2026].operating_profit | 50.348 | 50.348 | extracted_high_confidence | 455 | correct |
| [FY2025].operating_profit | 34.372 | 34.372 | extracted_high_confidence | 455 | correct |
| [FY2024].operating_profit | 27.327 | 27.327 | extracted_high_confidence | 455 | correct |
| [FY2026].net_worth | 131.206 | 131.206 | extracted_high_confidence | 455 | correct |
| [FY2025].net_worth | 94.721 | 94.721 | extracted_high_confidence | 455 | correct |
| [FY2024].net_worth | 70.449 | 70.449 | extracted_high_confidence | 455 | correct |

### m-k-c-agro-fresh-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 120.2564 | 120.2564 | extracted_high_confidence | 479 | correct |
| [FY2025].net_tangible_assets | 105.7112 | 105.7112 | extracted_high_confidence | 479 | correct |
| [FY2024].net_tangible_assets | 89.0328 | 89.0328 | extracted_high_confidence | 479 | correct |
| [FY2026].monetary_assets | 12.9943 | 12.9943 | extracted_high_confidence | 479 | correct |
| [FY2025].monetary_assets | 5.3367 | 5.3367 | extracted_high_confidence | 479 | correct |
| [FY2024].monetary_assets | 2.7646 | 2.7646 | extracted_high_confidence | 479 | correct |
| [FY2026].operating_profit | 52.0764 | 52.0764 | extracted_high_confidence | 479 | correct |
| [FY2025].operating_profit | 34.3971 | 34.3971 | extracted_high_confidence | 479 | correct |
| [FY2024].operating_profit | 35.1115 | 35.1115 | extracted_high_confidence | 479 | correct |
| [FY2026].net_worth | 133.2708 | 133.2708 | extracted_high_confidence | 479 | correct |
| [FY2025].net_worth | 111.0836 | 111.0836 | extracted_high_confidence | 479 | correct |
| [FY2024].net_worth | 91.8317 | 91.8317 | extracted_high_confidence | 479 | correct |

### maharashtra-oil-extractions-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 464.343 | 464.343 | extracted_high_confidence | 487 | correct |
| [FY2025].net_tangible_assets | 378.443 | 378.443 | extracted_high_confidence | 487 | correct |
| [FY2024].net_tangible_assets | 300.346 | 300.346 | extracted_high_confidence | 487 | correct |
| [FY2026].monetary_assets | 29.723 | 29.723 | extracted_high_confidence | 487 | correct |
| [FY2025].monetary_assets | 40.396 | 40.396 | extracted_high_confidence | 487 | correct |
| [FY2024].monetary_assets | 310.547 | 310.547 | extracted_high_confidence | 487 | correct |
| [FY2026].operating_profit | 121.025 | 121.025 | extracted_high_confidence | 487 | correct |
| [FY2025].operating_profit | 115.704 | 115.704 | extracted_high_confidence | 487 | correct |
| [FY2024].operating_profit | 40.781 | 40.781 | extracted_high_confidence | 487 | correct |
| [FY2026].net_worth | 461.027 | 461.027 | conflicting_candidates | 487 | correct |
| [FY2025].net_worth | 374.737 | 374.737 | conflicting_candidates | 487 | correct |
| [FY2024].net_worth | 295.731 | 295.731 | extracted_high_confidence | 487 | correct |

### ultravibrant-integrated-energy-limited-drhp

| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |
|---|---|---|---|---|---|
| [FY2026].net_tangible_assets | 41.9059 | 41.9059 | extracted_high_confidence | 474 | correct |
| [FY2025].net_tangible_assets | 17.8229 | 17.8229 | extracted_high_confidence | 474 | correct |
| [FY2024].net_tangible_assets | 2.2375 | 2.2375 | extracted_high_confidence | 474 | correct |
| [FY2026].monetary_assets | 4.2154 | 4.2154 | extracted_high_confidence | 474 | correct |
| [FY2025].monetary_assets | 32.3599 | 32.3599 | extracted_high_confidence | 474 | correct |
| [FY2024].monetary_assets | 2.0722 | 2.0722 | extracted_high_confidence | 474 | correct |
| [FY2026].operating_profit | 53.7729 | 53.7729 | extracted_high_confidence | 474 | correct |
| [FY2025].operating_profit | 26.6242 | 26.6242 | extracted_high_confidence | 474 | correct |
| [FY2024].operating_profit | 2.1367 | 2.1367 | extracted_high_confidence | 474 | correct |
| [FY2026].net_worth | 56.3041 | 56.3041 | extracted_high_confidence | 474 | correct |
| [FY2025].net_worth | 22.3110 | 22.3110 | extracted_high_confidence | 474 | correct |
| [FY2024].net_worth | 2.3405 | 2.3405 | extracted_high_confidence | 474 | correct |

