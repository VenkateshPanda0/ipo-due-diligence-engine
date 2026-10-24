"""Draft label files pre-filled from the extractor, for a labeller to confirm or correct.

Pre-filling saves typing, but it also anchors the labeller on the extractor's answer. Drafts are
therefore marked unreviewed, carry the suggestion in a separate field, and are never read as
ground truth; the labeller must read the cited page and write the label from it.
"""

from __future__ import annotations

from datetime import date

from redherring.eval.labels import Label, LabelFile
from redherring.eval.metrics import Prediction


def draft_from_predictions(doc_id: str, doc_sha256: str, preds: list[Prediction]) -> LabelFile:
    fields = [
        Label(
            key=p.key,
            status="unreviewed",
            suggested_rupees=p.value,
            pages=[p.pdf_page],
            span=p.span,
            note="Draft from the extractor: read the cited page and write the label from it.",
        )
        for p in sorted(preds, key=lambda x: x.key)
    ]
    return LabelFile(
        doc_id=doc_id,
        doc_sha256=doc_sha256,
        labelled_by="DRAFT (extractor pre-fill; not ground truth)",
        labelled_on=date.today(),
        method="pre-filled by `rh label-init`; replace with how the final labels were produced",
        fields=fields,
    )
