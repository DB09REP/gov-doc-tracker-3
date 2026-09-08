"""Namespaced RSS fields used by the tracker feeds."""

from feedgen.ext.base import BaseEntryExtension, BaseExtension
from lxml import etree


NAMESPACE = "https://gov-doc-tracker.local/rss/1.0"


class GovExtension(BaseExtension):
    def extend_ns(self):
        return {"gov": NAMESPACE}


class GovEntryExtension(BaseEntryExtension):
    def __init__(self):
        self.values = {}

    def fields(self, values=None):
        if values is not None:
            self.values = {key: value for key, value in values.items() if value not in (None, "")}
        return self.values

    def extend_rss(self, entry):
        names = {
            "company_name": "company",
            "entity_name": "entity",
            "department_name": "department",
            "amount": "amount",
            "amount_type": "amountType",
            "event_date": "eventDate",
        }
        for key, tag in names.items():
            if key not in self.values:
                continue
            element = etree.SubElement(entry, f"{{{NAMESPACE}}}{tag}")
            element.text = str(self.values[key])
            if key == "amount" and self.values.get("amount_currency"):
                element.set("currency", str(self.values["amount_currency"]))
        return entry

    def extend_atom(self, entry):
        return entry
