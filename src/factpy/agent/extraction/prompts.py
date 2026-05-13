from __future__ import annotations

from typing import Any

from ..documents import DocumentSegment
from ..errors import AgentContractError

SYSTEM_PROMPT_TEMPLATE = """You are a knowledge extraction assistant.
Your task is to extract structured facts from a text segment,
using ONLY the entity types and predicates defined in the provided schema.

Rules:
1. Only propose facts that can be expressed with the given schema.
2. Do not invent new entity types or predicates.
3. Only extract facts directly supported by the text.
4. If no valid facts can be extracted, return an empty proposals list.
5. Do not generate provenance fields (doc_id, segment_id, offsets) — those are injected by the system.
6. Assign a confidence score (0.0-1.0) based on how directly the text supports the fact.

Response format (strict contract — proposals that violate these rules will be rejected):

7. Each predicate in the schema is written as:
     - pred_id subject=<arg0_spec> field_values=[<arg1_spec>, <arg2_spec>, ...]
   The `subject=...` part is the predicate's first argument (arg 0) and represents
   the entity the fact is about. The `field_values=[...]` part lists the remaining
   arguments in order.

8. For each proposal you emit:
   - Put the subject entity's type in `entity_type` (must match one of the
     listed entity types).
   - Put the subject entity's identity field values in `entity_identity` as a
     list of `{{name, value}}` entries, one per identity field declared on that
     entity type. Use the entity's identity field names exactly as shown in
     the schema summary. Do NOT invent identity field names that are not in
     the schema summary.
   - Put the predicate ID in `pred_id` (must match one of the listed predicates).
   - Put the remaining arg values in `field_values` as a list of `{{tag, value}}`
     entries, one per slot in the `field_values=[...]` list shown in the schema
     summary. The order must match the schema summary.

9. `field_values` length contract:
   - `field_values.length` MUST equal the number of entries shown in the
     schema summary's `field_values=[...]` for that predicate.
   - Do NOT include the subject entity in `field_values` — it belongs in
     `entity_identity`.
   - If the predicate's schema summary shows `field_values=[]`, emit an
     empty list.

10. `field_values` tag contract:
    - For each entry, set `tag` to the arg's `type_domain` exactly as shown
      in the schema summary (the part after the colon, e.g. `string`, `int`,
      `entity_ref`).
    - Set `value` to the actual value, typed as one of: string, int, float,
      bool, or null.

Examples (study these before you answer — proposals that repeat these mistakes will be rejected):

Suppose the schema summary contains:
  Entities:
  - Doc identity=[title:string]
  Predicates:
  - doc:has_topic subject=arg0:entity_ref field_values=[arg1:string]

Example 1 — subject leakage (common mistake).

Source text: "The security handbook covers key rotation."

WRONG:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "entity_ref", value: "Doc:security handbook"}},
    {{tag: "string",     value: "key rotation"}}
  ]
  # length 2 — WRONG: the subject entity_ref is duplicated here; it already lives in entity_identity.

RIGHT:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "string", value: "key rotation"}}
  ]
  # length 1 — matches field_values=[arg1:string]. Subject lives only in entity_identity.

Example 2 — multi-entry overpacking (common mistake).

Source text: "The security handbook covers key rotation, TLS, and audit logging."

WRONG (one proposal):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "string", value: "key rotation"}},
    {{tag: "string", value: "TLS"}},
    {{tag: "string", value: "audit logging"}}
  ]
  # length 3 — WRONG: cramming three facts into one proposal's field_values.

RIGHT (three proposals, each length 1):
  proposal A:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "key rotation"}}]
  proposal B:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "TLS"}}]
  proposal C:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "audit logging"}}]
  # Each proposal carries exactly one fact. Enumeration in the source text becomes multiple proposals, not one bloated proposal.

Semantic Examples (content grounding — these rules decide WHAT strings are allowed as identity values and field values, and when to omit a specific proposal type for a segment while still emitting other valid proposals for the same segment):

Suppose the schema summary contains:
  Entities:
  - Doc identity=[title:string]
  - Mod identity=[mod_name:string]
  Predicates:
  - doc:has_topic subject=arg0:entity_ref field_values=[arg1:string]
  - mod:has_description subject=arg0:entity_ref field_values=[arg1:string]

Example 3 — Document title grounding.

Rule: Doc.title MUST be a stable identifier that appears VERBATIM in the source text (for example: a filename, a blueprint ID, a section anchor, or an explicit self-reference). If the source text does NOT contain a verbatim stable identifier that can serve as the Doc.title, emit NO Doc proposal for that segment.

Source text (has a verbatim stable identifier): "SECURITY.md documents the current key rotation policy."

RIGHT:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "SECURITY.md"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "key rotation policy"}}]
  # Doc.title "SECURITY.md" appears verbatim in the source text. Good grounding.

Source text (no verbatim stable identifier): "This document records the repository-level security hygiene rules."

WRONG (opaque identifier not in source):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "8e729d68d5deab3a"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "security hygiene rules"}}]
  # WRONG: "8e729d68d5deab3a" is an opaque hash and does NOT appear verbatim in the source text. This is a fabricated identity.

WRONG (synthesized from body prose):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "repository-level security hygiene rules"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "security hygiene rules"}}]
  # WRONG: the title is paraphrased from sentence content. A body prose phrase is not a stable identifier, even if it appears verbatim.

RIGHT (omit this proposal type):
  (Emit NO Doc proposal for this segment. The source text does not contain a verbatim stable identifier that could serve as Doc.title. Per-type abstention: if the same segment contains valid material for other entity types (for example a Mod proposal), still emit those — do NOT skip the entire segment. Rule 4's empty proposals list only applies when no valid proposals of any type can be made for the segment.)

Example 4 — Module description narrowing.

Rule: Mod.has_description's field value MUST be a DECLARATIVE description of what the module IS or DOES, not a plan, checklist, test expectation, acceptance criterion, or coverage label. If the source text only contains tasks or expectations for the module and no declarative description, emit NO Mod proposal for that segment.

Source text (has a declarative description): "AuthService handles token validation and user session management."

RIGHT:
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "handles token validation and user session management"}}]
  # The field value is a declarative description of what AuthService DOES. Good grounding.

Source text (checklist / task items, not declarative): "AuthService: [ ] Add MFA support. [ ] Rotate session keys weekly."

WRONG (task as description):
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "Add MFA support"}}]
  # WRONG: "Add MFA support" is a planned task, not a description of what AuthService currently is or does.

WRONG (acceptance / operational expectation as description):
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "Rotate session keys weekly"}}]
  # WRONG: "Rotate session keys weekly" is an operational expectation, not a declarative description.

RIGHT (omit this proposal type):
  (Emit NO Mod proposal for this segment. The source text only contains tasks and operational expectations for AuthService, not a declarative description of what it is or does. Per-type abstention: if the same segment contains valid material for other entity types (for example a Doc proposal grounded on a verbatim stable identifier), still emit those — do NOT skip the entire segment. Rule 4's empty proposals list only applies when no valid proposals of any type can be made for the segment.)

Example 5 — Module name grounding.

Rule: Mod.mod_name MUST be a software component identifier that appears VERBATIM in the source text (for example: a class name, a service name, a package name, a config variable, or a filename). Team names, organizational units, roles, and process names are NOT software components. If the source text mentions "data-infra team" as an owner or responsible party, do NOT extract it as a Mod — extract it as the owner field value of the Mod it maintains, if such a Mod is also present in the same segment.

Source text: "The data-infra team maintains AuthService and its deployment configs."

WRONG (team name as module identity):
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "data-infra team"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "maintains AuthService and its deployment configs"}}]
  # WRONG: "data-infra team" is an organizational unit, not a software component.

RIGHT:
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "handles token validation and deployment configs"}}]
  # "AuthService" is a software component name. Good grounding.

  (If the segment's ONLY mention of a module is indirect through a team name and no actual software component identifier appears verbatim, emit NO Mod proposal for that segment. Per-type abstention: if the same segment contains valid Doc proposals, still emit those.)

Schema:
{schema_summary}
"""

USER_PROMPT_TEMPLATE = """Extract facts from the following text segment.

Document: {doc_name}
Section: {section_label}
Page: {page_number}
Pattern type: {pattern_type}
Structural clarity: {structural_clarity:.2f}
{entity_context_block}

Text:
\"\"\"
{raw_text}
\"\"\"

Return a SegmentExtractionResponse with zero or more LLMFactProposal entries.
"""


def build_schema_summary(
    schema_ir: dict[str, Any],
    *,
    max_chars: int = 8000,
    entity_descriptions: dict[str, str] | None = None,
) -> str:
    """Build a deterministic prompt summary from schema IR.

    PS-01 / PS-02: every predicate `arg_spec` contributes a positional
    entry even if it lacks a `name`, and predicate lines mark the subject
    arg (arg0) explicitly so the LLM can map arg slots to entity_identity
    vs field_values.

    PS-05 (NOT applied): `identity_fields[]` that lack a canonical `name`
    are intentionally skipped. Canonical SchemaIR requires `name` on every
    identity field, so synthesizing a placeholder would teach the LLM to
    emit identity keys that downstream canonical validation rejects.
    """

    entities = schema_ir.get("entities", [])
    predicates = schema_ir.get("predicates", [])
    entity_lines: list[str] = ["Entities:"]
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            continue
        identity_entries: list[str] = []
        for field in entity.get("identity_fields", []):
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            type_domain = field.get("type_domain")
            if isinstance(name, str) and name:
                td_str = type_domain if isinstance(type_domain, str) and type_domain else "unknown"
                identity_entries.append(f"{name}:{td_str}")
        desc = ""
        if entity_descriptions and entity_type in entity_descriptions:
            desc = f"\n  ({entity_descriptions[entity_type]})"
        entity_lines.append(f"- {entity_type} identity=[{', '.join(identity_entries)}]{desc}")

    predicate_lines: list[str] = ["Predicates:"]
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        pred_id = predicate.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        arg_specs_raw = predicate.get("arg_specs", [])
        if not isinstance(arg_specs_raw, list):
            arg_specs_raw = []

        rendered_args: list[str] = []
        for idx, arg in enumerate(arg_specs_raw):
            if not isinstance(arg, dict):
                continue
            name = arg.get("name")
            type_domain = arg.get("type_domain")
            td_str = type_domain if isinstance(type_domain, str) and type_domain else "unknown"
            if isinstance(name, str) and name:
                rendered_args.append(f"{name}:{td_str}")
            else:
                rendered_args.append(f"arg{idx}:{td_str}")

        if rendered_args:
            subject = rendered_args[0]
            rest = rendered_args[1:]
            rest_str = ", ".join(rest)
            predicate_lines.append(
                f"- {pred_id} subject={subject} field_values=[{rest_str}]"
            )
        else:
            predicate_lines.append(f"- {pred_id} subject=<missing> field_values=[]")

    summary = "\n".join(entity_lines + [""] + predicate_lines)
    if len(summary) <= max_chars:
        return summary
    suffix = "\n...<schema_summary_truncated>"
    return summary[: max(0, max_chars - len(suffix))] + suffix


def truncate_prompt_text(raw_text: str, *, max_text_chars: int) -> str:
    if not isinstance(raw_text, str):
        raise AgentContractError("raw_text must be string")
    if not isinstance(max_text_chars, int) or max_text_chars <= 0:
        raise AgentContractError("max_text_chars must be positive int")
    return raw_text[:max_text_chars]


def format_entity_context_header(
    entries: list[dict[str, object]],
    *,
    max_context_chars: int = 2000,
) -> str:
    """Format accumulated entity mentions into a context header for the LLM.

    Each entry is a dict with keys: entity_type (str), identity (dict),
    facts (list[str]).  Returns empty string if entries is empty.
    """
    if not entries:
        return ""
    lines: list[str] = [
        "Previously identified entities in this document "
        "(use for reference resolution, do not re-extract these facts):"
    ]
    for entry in entries:
        etype = entry.get("entity_type", "?")
        identity = entry.get("identity", {})
        facts = entry.get("facts", [])
        id_str = ", ".join(f'{k}="{v}"' for k, v in identity.items())
        if facts:
            facts_str = ", ".join(facts)
            lines.append(f"- {etype} ({id_str}): {facts_str}")
        else:
            lines.append(f"- {etype} ({id_str})")

    result = "\n".join(lines)
    if len(result) <= max_context_chars:
        return result
    truncated = result[:max_context_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    return truncated + "\n... (context truncated)"


def format_gleaning_context(
    entity_entries: list[dict[str, object]],
    pass1_yield: int,
) -> str:
    """Build a gleaning-specific context header for second-pass extraction.

    Prepends a GLEANING PASS instruction to the full entity context header,
    telling the LLM this is a re-examination and to focus on missed facts.
    Returns empty string if entity_entries is empty.
    """
    if not entity_entries:
        return ""
    prefix = (
        f"GLEANING PASS: This segment was previously examined and yielded "
        f"{pass1_yield} fact(s). Re-examine the text for ADDITIONAL facts "
        f"about the known entities below that were missed in the first pass. "
        f"Focus on facts the first pass may have missed due to limited context. "
        f"Do not re-extract facts that duplicate what was found previously."
    )
    entity_header = format_entity_context_header(entity_entries)
    if not entity_header:
        return prefix
    return prefix + "\n\n" + entity_header


def build_messages(
    *,
    segment: DocumentSegment,
    schema_summary: str,
    raw_text_for_llm: str,
    prior_entity_context: str = "",
    source_doc_name: str | None = None,
) -> list[dict[str, str]]:
    """Build the system/user message pair for extraction."""

    if not isinstance(segment, DocumentSegment):
        raise AgentContractError("segment must be DocumentSegment")
    if not isinstance(schema_summary, str) or not schema_summary:
        raise AgentContractError("schema_summary must be non-empty string")
    if not isinstance(raw_text_for_llm, str):
        raise AgentContractError("raw_text_for_llm must be string")
    section_label = segment.section_label or "(none)"
    page_number = "n/a" if segment.page_number is None else str(segment.page_number)
    return [
        {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(schema_summary=schema_summary)},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                doc_name=source_doc_name if source_doc_name else segment.doc_id,
                section_label=section_label,
                page_number=page_number,
                pattern_type=segment.pattern_type,
                structural_clarity=segment.structural_clarity,
                raw_text=raw_text_for_llm,
                entity_context_block=prior_entity_context,
            ),
        },
    ]
