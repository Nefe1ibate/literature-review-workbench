#!/usr/bin/env python3
"""Portable literature-review records and deterministic integrity checks.

This helper uses no network, model, PDF parser, or profile-supplied executable.
It checks provenance and dependencies, never scientific entailment.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid


SCHEMA = "literature-review-state/1"
PROFILE_SCHEMA = "literature-domain-profile/1"
COLLECTIONS = ("papers", "sources", "evidence", "claims", "sections", "paragraphs",
               "reviews", "searches", "check_results")
CLAIM_KINDS = {"source_result", "synthesis", "interpretation", "proposed_gap"}
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ENUMS = {
    "papers": {"status": {"candidate", "included", "excluded", "pending"},
               "read_status": {"unread", "metadata_only", "partial", "full"}},
    "sources": {"kind": {"pdf", "text", "html", "other"}},
    "claims": {"kind": CLAIM_KINDS,
               "status": {"draft", "verified", "needs_review", "rejected", "unassessable"}},
    "sections": {"status": {"planned", "draft", "accepted", "needs_review"}},
    "paragraphs": {"status": {"planned", "draft", "accepted", "needs_review"}},
    "reviews": {"target_type": {"claim", "paragraph", "section"},
                "action": {"ACCEPT", "DIRECT_EDIT", "REPLAN_PARAGRAPH", "REPLAN_SECTION"},
                "status": {"open", "resolved", "unassessable"}},
    "check_results": {"status": {"pass", "fail", "unassessable"}},
}
REQUIRED = {
    "papers": ("id", "title", "authors", "status", "read_status"),
    "sources": ("id", "paper_id", "kind", "path", "sha256", "version_label"),
    "evidence": ("id", "paper_id", "source_id", "locator", "verification"),
    "claims": ("id", "text", "kind", "status", "evidence_ids"),
    "sections": ("id", "title", "objective", "status"),
    "paragraphs": ("id", "section_id", "role", "claim_ids", "status"),
    "reviews": ("id", "target_type", "target_id", "action", "reason", "status"),
    "searches": ("id", "query", "provider", "searched_at"),
    "check_results": ("id", "claim_id", "profile_id", "rule_id", "status", "reviewer",
                      "rationale", "claim_sha256", "profile_sha256"),
}
TARGET_COLLECTIONS = {"claim": "claims", "paragraph": "paragraphs", "section": "sections"}
_UNSET = object()
PROJECT_FIELDS = {"topic", "language", "cutoff", "mode", "require_fulltext", "research_questions",
                  "questions", "inclusion_criteria", "criteria", "exclusions", "deliverable_limits", "extensions"}


class WorkbenchError(Exception):
    """A rejected operation, with no committed state mutation."""


class ConflictError(WorkbenchError):
    """Another writer or an unexpected revision prevented the commit."""


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def content_hash(record):
    """Claim fingerprint: canonical UTF-8 JSON, excluding top-level status only."""
    return hashlib.sha256(canonical_bytes({k: v for k, v in record.items()
                                          if k != "status"})).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkbenchError("Duplicate JSON object key: " + key)
        result[key] = value
    return result


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_json_no_duplicates,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              WorkbenchError("Non-finite JSON number: " + value)))
    except (OSError, ValueError) as exc:
        raise WorkbenchError("Cannot read JSON {}: {}".format(path, exc)) from exc


def resolve_path(root, path):
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(root) / candidate


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


class _Lock:
    def __init__(self, root):
        self.path = Path(root) / ".workbench.lock"
        self.fd = None

    def __enter__(self):
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, json_bytes({"pid": os.getpid(), "created_at": now()}))
            os.fsync(self.fd)
        except FileExistsError as exc:
            raise ConflictError("Workspace is locked by another write; retry after it finishes. "
                                "After a crashed process, inspect .workbench.lock before removing it.") from exc
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.path.unlink()


def read_state(root):
    state = read_json(Path(root) / "state.json")
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA:
        raise WorkbenchError("Not a literature-review-state/1 workspace")
    return state


def _index(state, collection):
    return {record.get("id"): record for record in state.get(collection, [])
            if isinstance(record, dict) and isinstance(record.get("id"), str)}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_hash(value):
    return isinstance(value, str) and bool(HASH_PATTERN.fullmatch(value))


def _source_facts(root, source):
    path_value = source.get("path")
    if not _nonempty(path_value):
        return {"available": False, "digest": None, "path": None, "reason": "No local source path"}
    path = resolve_path(root, path_value)
    try:
        digest = file_hash(path)
        return {"available": True, "digest": digest, "path": path,
                "current": digest == source.get("sha256")}
    except OSError as exc:
        return {"available": False, "digest": None, "path": path,
                "reason": "Source unavailable: " + str(exc)}


def _profile_facts(root, state):
    spec = state.get("project", {}).get("domain_profile")
    if spec is None:
        return {"configured": False, "available": True, "current": True, "profile": None}
    if not isinstance(spec, dict) or not _nonempty(spec.get("path")):
        return {"configured": True, "available": False, "current": False,
                "error": "Profile needs path and sha256"}
    path = resolve_path(root, spec["path"])
    try:
        profile = read_json(path)
        digest = file_hash(path)
        if not isinstance(profile, dict):
            raise WorkbenchError("Domain profile must be a JSON object")
        instructions_digest, instructions_path, instructions_error = None, None, None
        if profile.get("instructions_path") is not None:
            if not _nonempty(profile["instructions_path"]):
                raise WorkbenchError("Profile instructions_path must be a nonempty string")
            instructions_path = resolve_path(path.parent, profile["instructions_path"])
            try:
                instructions_digest = file_hash(instructions_path)
            except OSError as exc:
                instructions_error = str(exc)
        resource_current = instructions_error is None and instructions_digest == spec.get("instructions_sha256")
        return {"configured": True, "available": True,
                "current": digest == spec.get("sha256") and resource_current,
                "profile_current": digest == spec.get("sha256"), "resource_current": resource_current,
                "profile": profile, "digest": digest, "path": path,
                "instructions_path": instructions_path, "instructions_digest": instructions_digest,
                "instructions_error": instructions_error}
    except (OSError, WorkbenchError) as exc:
        return {"configured": True, "available": False, "current": False, "error": str(exc)}


def _profile_errors(profile):
    errors = []
    if profile.get("schema_version") != PROFILE_SCHEMA:
        errors.append("Invalid profile schema_version")
    for field in ("id", "version", "name"):
        if not _nonempty(profile.get(field)):
            errors.append("Profile {} must be a nonempty string".format(field))
    if "instructions_path" in profile and not _nonempty(profile["instructions_path"]):
        errors.append("Profile instructions_path must be a nonempty string")
    checks = profile.get("checks")
    if not isinstance(checks, list):
        return errors + ["Profile checks must be an array"]
    ids = set()
    for check in checks:
        if not isinstance(check, dict):
            errors.append("Profile check must be an object")
            continue
        rid = check.get("id")
        if not _nonempty(rid) or rid in ids:
            errors.append("Profile check IDs must be nonempty and unique")
        ids.add(str(rid))
        for field in ("label", "question"):
            if not _nonempty(check.get(field)):
                errors.append("Profile check {} lacks {}".format(rid, field))
        applies = check.get("applies_to")
        if (not isinstance(applies, list) or not applies or
                any(not isinstance(kind, str) or kind not in CLAIM_KINDS for kind in applies)):
            errors.append("Profile check {} has invalid applies_to".format(rid))
        if not isinstance(check.get("severity"), str) or check.get("severity") not in {"critical", "advisory"}:
            errors.append("Profile check {} has invalid severity".format(rid))
        if not isinstance(check.get("requires_source"), bool):
            errors.append("Profile check {} requires boolean requires_source".format(rid))
    return errors


def _current_evidence(record, sources, facts):
    source = sources.get(record.get("source_id"), {})
    fact = facts.get(record.get("source_id"), {})
    verification = record.get("verification", {})
    return (isinstance(verification, dict) and verification.get("status") == "supported"
            and _nonempty(verification.get("reviewer")) and _nonempty(verification.get("method"))
            and fact.get("available") and fact.get("current")
            and verification.get("source_sha256") == source.get("sha256")
            and _valid_hash(verification.get("source_sha256")))


def _applicable_checks(profile, claim, severity=None):
    if not profile:
        return []
    return [check for check in profile.get("checks", []) if isinstance(check, dict)
            and claim.get("kind") in check.get("applies_to", [])
            and (severity is None or check.get("severity") == severity)]


def _domain_decision(state, claim, profile_facts, evidence_current):
    if not profile_facts["configured"]:
        return "pass"
    if not profile_facts.get("available") or not profile_facts.get("current"):
        return "unassessable"
    profile = profile_facts["profile"]
    decisions = []
    for rule in _applicable_checks(profile, claim, "critical"):
        results = [result for result in state.get("check_results", [])
                   if result.get("claim_id") == claim.get("id")
                   and result.get("profile_id") == profile.get("id")
                   and result.get("rule_id") == rule.get("id")]
        valid = [result for result in results
                 if result.get("claim_sha256") == content_hash(claim)
                 and result.get("profile_sha256") == profile_facts.get("digest")
                 and result.get("instructions_sha256") == profile_facts.get("instructions_digest")
                 and _nonempty(result.get("reviewer")) and _nonempty(result.get("rationale"))
                 and (not rule.get("requires_source") or
                      (result.get("evidence_ids") and
                       all(evidence_current.get(eid, False) for eid in result.get("evidence_ids", []))))]
        if any(result.get("status") == "fail" for result in valid):
            decisions.append("fail")
        elif len(valid) == 1:
            decisions.append(valid[0].get("status", "unassessable"))
        else:
            decisions.append("unassessable")
    return "fail" if "fail" in decisions else "unassessable" if "unassessable" in decisions else "pass"


def validate_state(state, root):
    """Read-only validation. Missing/unknown cases never count as correct cases."""
    report = {"schema_version": "literature-validation/1", "revision": state.get("revision"),
              "checked_at": now(), "errors": [], "warnings": [], "unassessable": [],
              "limitation": "Deterministic checks establish record integrity and source identity, "
                            "not semantic correctness or scientific validity."}

    def add(level, code, message, record_id=None, collection=None):
        item = {"code": code, "message": message}
        if record_id is not None:
            item["id"] = record_id
        if collection:
            item["collection"] = collection
        report[level].append(item)

    if state.get("schema_version") != SCHEMA:
        add("errors", "schema", "Invalid state schema_version")
    if not _is_integer(state.get("revision")) or state["revision"] < 0:
        add("errors", "revision", "Revision must be a nonnegative integer")
    project = state.get("project", {})
    if not isinstance(project, dict):
        project = {}
        add("errors", "project", "Project must be an object")
    for field in ("id", "topic", "language"):
        if not _nonempty(project.get(field)):
            add("errors", "project", "Project needs nonempty " + field)
    if not isinstance(project.get("mode"), str) or project.get("mode") not in {"focused", "comprehensive", "systematic-prep"}:
        add("errors", "project_mode", "Invalid review mode")
    if not isinstance(project.get("require_fulltext"), bool):
        add("errors", "fulltext_flag", "require_fulltext must be boolean")
    cutoff = project.get("cutoff")
    if cutoff is not None:
        try:
            if not isinstance(cutoff, str) or dt.date.fromisoformat(cutoff).isoformat() != cutoff:
                raise ValueError()
        except ValueError:
            add("errors", "cutoff", "Cutoff must be an ISO date or null")

    usable = copy.copy(state)
    for collection in COLLECTIONS:
        records = state.get(collection)
        if not isinstance(records, list):
            add("errors", "collection", collection + " must be an array")
            usable[collection] = []
            continue
        ids = set()
        for record in records:
            if not isinstance(record, dict):
                add("errors", "record", "Record must be an object", collection=collection)
                continue
            rid = record.get("id")
            if not _nonempty(rid):
                add("errors", "id", "ID must be a nonempty string", collection=collection)
            elif rid in ids:
                add("errors", "duplicate_id", "Duplicate record ID", rid, collection)
            ids.add(str(rid))
            for field in REQUIRED[collection]:
                if field not in record:
                    add("errors", "required", "Missing field " + field, rid, collection)
            for field, allowed in ENUMS.get(collection, {}).items():
                if not isinstance(record.get(field), str) or record.get(field) not in allowed:
                    add("errors", "enum", "Invalid " + field, rid, collection)
            if "extensions" in record and not isinstance(record["extensions"], dict):
                add("errors", "extensions", "extensions must be a namespaced object", rid, collection)
            for field in ("authors", "evidence_ids", "search_ids", "paper_ids", "claim_ids"):
                if field in record and (not isinstance(record[field], list) or any(
                        not isinstance(value, str) for value in record[field])):
                    add("errors", "list_type", field + " must be a list of strings", rid, collection)
            for field in ("paper_id", "source_id", "section_id", "parent_id", "primary_source_id", "target_id"):
                if field in record and record[field] is not None and not _nonempty(record[field]):
                    add("errors", "reference_type", field + " must be a nonempty string", rid, collection)
            if collection == "evidence" and (not isinstance(record.get("verification"), dict) or
                    not isinstance(record.get("verification", {}).get("status"), str)):
                add("errors", "verification_type", "verification requires an object with string status", rid, collection)
        usable[collection] = [record for record in records if isinstance(record, dict)]
    if report["errors"]:
        report["coverage"] = {"unassessable": "Structural errors prevent safe coverage enumeration"}
        report["verdict"] = "fail"
        return report
    state = usable
    indices = {collection: _index(state, collection) for collection in COLLECTIONS}
    papers, sources, evidence = (indices[name] for name in ("papers", "sources", "evidence"))
    claims, sections = (indices[name] for name in ("claims", "sections"))

    def foreign(value, target, rid, collection, field):
        if not isinstance(value, str) or value not in indices[target]:
            add("errors", "foreign_key", "{} references missing {}".format(field, target), rid, collection)
            return False
        return True

    def foreign_list(record, field, target, collection, required=False):
        if field not in record and not required:
            return []
        values = record.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            add("errors", "list_type", field + " must be a list of IDs", record.get("id"), collection)
            return []
        if len(set(values)) != len(values):
            add("errors", "duplicate_reference", field + " contains duplicate IDs", record.get("id"), collection)
        for value in values:
            foreign(value, target, record.get("id"), collection, field)
        return values

    for paper in state["papers"]:
        rid = paper.get("id")
        if not _nonempty(paper.get("title")) or not isinstance(paper.get("authors"), list) or any(
                not _nonempty(author) for author in paper.get("authors", [])):
            add("errors", "paper_metadata", "Paper needs a title and a string author list", rid, "papers")
        if paper.get("primary_source_id") is not None and foreign(
                paper["primary_source_id"], "sources", rid, "papers", "primary_source_id"):
            if sources[paper["primary_source_id"]].get("paper_id") != rid:
                add("errors", "paper_source", "Primary source belongs to another paper", rid, "papers")
        if project.get("require_fulltext") and paper.get("status") == "included":
            if paper.get("read_status") != "full":
                add("unassessable", "reading_incomplete", "Included paper has not been fully read", rid, "papers")
            if paper.get("missing_parts"):
                add("unassessable", "missing_parts", "Paper has explicitly missing parts", rid, "papers")
    facts = {}
    for source in state["sources"]:
        rid = source.get("id")
        foreign(source.get("paper_id"), "papers", rid, "sources", "paper_id")
        if source.get("path") is not None and not _nonempty(source.get("path")):
            add("errors", "source_path", "Source path must be a nonempty string or null", rid, "sources")
        if source.get("sha256") is not None and not _valid_hash(source.get("sha256")):
            add("errors", "source_digest", "Source sha256 must be a lowercase file digest or null", rid, "sources")
        if not _nonempty(source.get("version_label")):
            add("errors", "source_version", "Source requires version_label", rid, "sources")
        count = source.get("page_count")
        if count is not None and (not _is_integer(count) or count < 1):
            add("errors", "page_count", "page_count must be a positive integer", rid, "sources")
        fact = _source_facts(root, source)
        facts[rid] = fact
        if not fact["available"]:
            add("unassessable", "missing_source", fact["reason"], rid, "sources")
        elif not fact.get("current"):
            add("warnings", "stale_source", "Source bytes differ from the recorded digest", rid, "sources")
        if source.get("missing_parts"):
            add("unassessable", "source_missing_parts", "Source lists missing parts", rid, "sources")
    evidence_current = {}
    for item in state["evidence"]:
        rid = item.get("id")
        foreign(item.get("paper_id"), "papers", rid, "evidence", "paper_id")
        foreign(item.get("source_id"), "sources", rid, "evidence", "source_id")
        source = sources.get(item.get("source_id"), {})
        fact = facts.get(item.get("source_id"), {})
        prior_verification = item.get("verification", {})
        stale_locator = (prior_verification.get("status") == "pending" and
                         _valid_hash(prior_verification.get("source_sha256")) and
                         prior_verification.get("source_sha256") != source.get("sha256"))
        if source and source.get("paper_id") != item.get("paper_id"):
            add("errors", "evidence_paper", "Evidence paper and source paper differ", rid, "evidence")
        if not _nonempty(item.get("excerpt")) and not _nonempty(item.get("paraphrase")):
            add("errors", "evidence_text", "Evidence needs an excerpt or paraphrase", rid, "evidence")
        locator = item.get("locator")
        fields = {"pdf_page", "printed_page", "section", "equation", "table", "proposition", "anchor", "line_start"}
        if not isinstance(locator, dict) or not any(
                locator.get(field) not in (None, "", []) for field in fields):
            add("errors", "locator", "Evidence needs a specific source location", rid, "evidence")
            locator = {}
        if "pdf_page" in locator:
            page = locator["pdf_page"]
            if source.get("kind") != "pdf":
                add("errors", "pdf_locator", "Physical PDF pages apply only to PDF sources", rid, "evidence")
            if not _is_integer(page) or page < 1:
                add("errors", "pdf_page", "PDF pages are one-based integers", rid, "evidence")
            elif _is_integer(source.get("page_count")) and page > source["page_count"]:
                add("unassessable" if stale_locator else "errors", "page_bounds",
                    "PDF page is outside the declared page count; stale locations require relocation", rid, "evidence")
        if "line_end" in locator and "line_start" not in locator:
            add("errors", "line_locator", "line_end requires line_start", rid, "evidence")
        if "line_start" in locator:
            start, end = locator["line_start"], locator.get("line_end", locator["line_start"])
            if not _is_integer(start) or not _is_integer(end) or start < 1 or end < start:
                add("errors", "line_bounds", "Text lines must be ordered one-based integers", rid, "evidence")
            elif source.get("kind") not in {"text", "html"}:
                add("errors", "line_source", "Line locations require text or HTML sources", rid, "evidence")
            elif fact.get("available"):
                try:
                    line_count = len(fact["path"].read_text(encoding="utf-8-sig").splitlines())
                    if end > line_count:
                        add("unassessable" if stale_locator else "errors", "line_bounds",
                            "Text line is outside the local source; stale locations require relocation", rid, "evidence")
                except (OSError, UnicodeError):
                    add("unassessable", "text_encoding", "Cannot inspect source text lines as UTF-8", rid, "evidence")
        for field in fields - {"pdf_page", "line_start"}:
            if field in locator and (not isinstance(locator[field], (str, int)) or isinstance(locator[field], bool)
                                     or not str(locator[field]).strip()):
                add("errors", "locator_value", "Invalid location " + field, rid, "evidence")
        verification = item.get("verification")
        if not isinstance(verification, dict) or verification.get("status") not in {
                "pending", "supported", "contradicted", "insufficient"}:
            add("errors", "verification", "Evidence has invalid verification status", rid, "evidence")
            verification = {}
        if verification.get("status") == "supported":
            if not _nonempty(verification.get("reviewer")) or not _nonempty(verification.get("method")):
                add("errors", "verification_provenance", "Supported evidence needs reviewer and method", rid, "evidence")
            if not _valid_hash(verification.get("source_sha256")):
                add("errors", "verification_digest", "Supported evidence needs source_sha256", rid, "evidence")
            if verification.get("source_sha256") != source.get("sha256") or not fact.get("current"):
                add("warnings", "stale_evidence", "Evidence is not verified against current local source bytes", rid, "evidence")
        evidence_current[rid] = bool(_current_evidence(item, sources, facts))
        if not evidence_current[rid]:
            add("unassessable", "evidence_not_supported", "Evidence lacks current source-aligned support", rid, "evidence")

    profile_facts = _profile_facts(root, state)
    profile = profile_facts.get("profile")
    profile_spec = project.get("domain_profile")
    if profile_spec is not None:
        if not isinstance(profile_spec, dict) or not _valid_hash(profile_spec.get("sha256")):
            add("errors", "profile_digest", "Configured profile requires a file sha256")
        if isinstance(profile_spec, dict) and "instructions_sha256" in profile_spec and not _valid_hash(profile_spec["instructions_sha256"]):
            add("errors", "instructions_digest", "Linked domain instructions require a file sha256")
        if not profile_facts.get("available"):
            add("unassessable", "profile_missing", profile_facts.get("error", "Profile unavailable"))
        elif not profile_facts.get("current"):
            add("warnings", "profile_stale", "Domain profile bytes changed; old decisions are stale")
        if profile_facts.get("instructions_error"):
            add("unassessable", "profile_instructions_missing", "Linked domain instructions are unavailable")
        if profile:
            profile_errors = _profile_errors(profile)
            for message in profile_errors:
                add("errors", "profile_schema", message)
            if profile_errors:
                profile = None
                profile_facts["available"] = False
    domain_decisions = {}
    for claim in state["claims"]:
        rid = claim.get("id")
        if not _nonempty(claim.get("text")):
            add("errors", "claim_text", "Claim needs nonempty text", rid, "claims")
        evidence_ids = foreign_list(claim, "evidence_ids", "evidence", "claims", True)
        search_ids = foreign_list(claim, "search_ids", "searches", "claims")
        if "priority_claim" in claim and not isinstance(claim["priority_claim"], bool):
            add("errors", "priority_flag", "priority_claim must be boolean", rid, "claims")
        if "absence_claim" in claim and not isinstance(claim["absence_claim"], bool):
            add("errors", "absence_flag", "absence_claim must be boolean", rid, "claims")
        supported = bool(evidence_ids) and all(evidence_current.get(eid, False) for eid in evidence_ids)
        if claim.get("status") == "verified" and not supported:
            add("errors", "verified_claim", "Verified claim requires only current supported evidence", rid, "claims")
        if claim.get("status") == "verified" and (claim.get("priority_claim") or claim.get("absence_claim")
                                                   or claim.get("kind") == "proposed_gap"):
            scope = claim.get("comparison_scope")
            scope_present = bool(scope) if isinstance(scope, (dict, list)) else _nonempty(scope)
            searches_scoped = bool(search_ids) and all(_nonempty(indices["searches"].get(sid, {}).get("scope_note"))
                                                      or indices["searches"].get(sid, {}).get("filters") for sid in search_ids)
            if not scope_present:
                add("errors", "comparison_scope", "Verified research proposals, absence and priority claims need an explicit comparison scope", rid, "claims")
            if (claim.get("priority_claim") or claim.get("absence_claim")) and not searches_scoped:
                add("errors", "priority_scope", "Absence/priority requires search scope and comparison evidence; "
                    "it is not a novelty certificate", rid, "claims")
        decision = _domain_decision(state, claim, profile_facts, evidence_current)
        domain_decisions[rid] = decision
        if claim.get("status") == "verified" and decision == "unassessable":
            add("unassessable", "critical_check_missing", "Verified claim lacks current applicable critical domain decisions", rid, "claims")
        if claim.get("status") == "verified" and decision == "fail":
            add("warnings", "critical_check_failed", "Claim has a current critical domain failure", rid, "claims")
        if claim.get("status") in {"draft", "needs_review", "unassessable"}:
            add("unassessable", "claim_pending", "Claim has not completed verification", rid, "claims")

    def acceptance(record, claim_ids, collection):
        if record.get("status") != "accepted":
            return
        for cid in claim_ids:
            if claims.get(cid, {}).get("status") != "verified":
                add("errors", "accepted_claim", "Accepted prose relies on an unverified/rejected claim", record.get("id"), collection)
            if domain_decisions.get(cid, "unassessable") != "pass":
                add("errors", "accepted_domain", "Accepted prose lacks passing critical domain checks", record.get("id"), collection)

    for section in state["sections"]:
        rid = section.get("id")
        for field in ("title", "objective"):
            if not _nonempty(section.get(field)):
                add("errors", "section_text", "Section needs " + field, rid, "sections")
        if section.get("parent_id") is not None:
            foreign(section["parent_id"], "sections", rid, "sections", "parent_id")
        foreign_list(section, "paper_ids", "papers", "sections")
        claim_ids = foreign_list(section, "claim_ids", "claims", "sections")
        writing_claim_ids = set(claim_ids)
        descendants = {rid}
        while True:
            previous_size = len(descendants)
            descendants.update(s["id"] for s in state["sections"] if s.get("parent_id") in descendants)
            if len(descendants) == previous_size:
                break
        for paragraph in state["paragraphs"]:
            if paragraph.get("section_id") in descendants:
                writing_claim_ids.update(paragraph.get("claim_ids", []))
        for child in state["sections"]:
            if child.get("id") in descendants:
                writing_claim_ids.update(child.get("claim_ids", []))
        acceptance(section, writing_claim_ids, "sections")
        seen, node = set(), rid
        while node in sections:
            if node in seen:
                add("errors", "section_cycle", "Section parents contain a cycle", rid, "sections")
                break
            seen.add(node)
            node = sections[node].get("parent_id")
    for paragraph in state["paragraphs"]:
        rid = paragraph.get("id")
        foreign(paragraph.get("section_id"), "sections", rid, "paragraphs", "section_id")
        if not _nonempty(paragraph.get("role")):
            add("errors", "paragraph_role", "Paragraph needs an argument role", rid, "paragraphs")
        claim_ids = foreign_list(paragraph, "claim_ids", "claims", "paragraphs", True)
        paper_ids = foreign_list(paragraph, "paper_ids", "papers", "paragraphs")
        section = sections.get(paragraph.get("section_id"), {})
        used_papers = set(paper_ids)
        for cid in claim_ids:
            used_papers.update(evidence.get(eid, {}).get("paper_id")
                               for eid in claims.get(cid, {}).get("evidence_ids", []))
        used_papers.discard(None)
        if "paper_ids" in section and not used_papers.issubset(set(section.get("paper_ids", []))):
            add("errors", "paragraph_scope", "Paragraph's supporting papers exceed section scope", rid, "paragraphs")
        if "claim_ids" in section and not set(claim_ids).issubset(set(section.get("claim_ids", []))):
            add("errors", "paragraph_claim_scope", "Paragraph claims exceed section claim plan", rid, "paragraphs")
        acceptance(paragraph, claim_ids, "paragraphs")
        if paragraph.get("draft_path"):
            if not isinstance(paragraph["draft_path"], str):
                add("errors", "draft_path", "draft_path must be a string", rid, "paragraphs")
            elif not resolve_path(root, paragraph["draft_path"]).is_file():
                add("unassessable", "draft_missing", "Declared paragraph draft is unavailable", rid, "paragraphs")
    for review in state["reviews"]:
        collection = TARGET_COLLECTIONS.get(review.get("target_type"))
        if collection:
            foreign(review.get("target_id"), collection, review.get("id"), "reviews", "target_id")
        if not _nonempty(review.get("reason")):
            add("errors", "review_reason", "Review needs a reason", review.get("id"), "reviews")
        foreign_list(review, "evidence_ids", "evidence", "reviews")
    check_keys = set()
    for result in state["check_results"]:
        rid = result.get("id")
        foreign(result.get("claim_id"), "claims", rid, "check_results", "claim_id")
        result_evidence = foreign_list(result, "evidence_ids", "evidence", "check_results")
        for field in ("profile_id", "rule_id", "reviewer", "rationale"):
            if not _nonempty(result.get(field)):
                add("errors", "check_provenance", "Check result needs " + field, rid, "check_results")
        for field in ("claim_sha256", "profile_sha256"):
            if not _valid_hash(result.get(field)):
                add("errors", "check_digest", "Invalid " + field, rid, "check_results")
        if "instructions_sha256" in result and not _valid_hash(result["instructions_sha256"]):
            add("errors", "check_digest", "Invalid instructions_sha256", rid, "check_results")
        claim = claims.get(result.get("claim_id"), {})
        rules = {rule.get("id"): rule for rule in profile.get("checks", []) if isinstance(rule, dict)} if profile else {}
        rule = rules.get(result.get("rule_id"))
        matches_profile = bool(profile and result.get("profile_id") == profile.get("id"))
        fingerprint_current = matches_profile and profile_facts.get("current") and (
            result.get("profile_sha256") == profile_facts.get("digest") and
            result.get("instructions_sha256") == profile_facts.get("instructions_digest") and
            result.get("claim_sha256") == content_hash(claim))
        if matches_profile and not rule:
            add("warnings", "check_rule_removed", "Check rule is absent from selected profile", rid, "check_results")
        if rule and claim.get("kind") not in rule.get("applies_to", []):
            add("errors", "check_scope", "Check is not applicable to this claim kind", rid, "check_results")
        if result_evidence and not set(result_evidence).issubset(set(claim.get("evidence_ids", []))):
            add("errors", "check_evidence_scope", "Domain check evidence must belong to the claim", rid, "check_results")
        if fingerprint_current and result.get("status") in {"pass", "fail"}:
            key = (result.get("claim_id"), result.get("profile_id"), result.get("rule_id"))
            if key in check_keys:
                add("errors", "duplicate_check", "Duplicate current decision for claim/profile/rule", rid, "check_results")
            check_keys.add(key)
            if rule and rule.get("requires_source") and (
                    not result_evidence or not all(evidence_current.get(eid, False) for eid in result_evidence)):
                add("errors", "check_source", "Source-required check needs current supported claim evidence", rid, "check_results")
        elif result.get("status") != "unassessable":
            add("warnings", "stale_check", "Check result has stale claim/profile fingerprints", rid, "check_results")
    for search in state["searches"]:
        for field in ("query", "provider", "searched_at"):
            if not _nonempty(search.get(field)):
                add("errors", "search_metadata", "Search needs " + field, search.get("id"), "searches")
        if search.get("result_count") is not None and (not _is_integer(search["result_count"]) or search["result_count"] < 0):
            add("errors", "search_count", "result_count must be nonnegative integer or null", search.get("id"), "searches")

    included = [paper for paper in state["papers"] if paper.get("status") == "included"]
    supported_count = sum(evidence_current.values())
    assessed_count = supported_count + sum(
        item.get("verification", {}).get("status") == "contradicted" and
        facts.get(item.get("source_id"), {}).get("current", False) and
        item.get("verification", {}).get("source_sha256") == sources.get(item.get("source_id"), {}).get("sha256")
        and _nonempty(item.get("verification", {}).get("reviewer")) and _nonempty(item.get("verification", {}).get("method"))
        for item in state["evidence"] if isinstance(item.get("verification"), dict))
    report["coverage"] = {
        "papers": {"included": len(included), "full_read": sum(p.get("read_status") == "full" for p in included),
                   "missing_parts": sum(bool(p.get("missing_parts")) for p in included)},
        "sources": {"total": len(sources), "current_local": sum(bool(f.get("current")) for f in facts.values()),
                    "missing_local": sum(not f.get("available") for f in facts.values())},
        "evidence": {"total": len(evidence), "current_supported": supported_count,
                     "source_aligned_decisions_denominator": assessed_count,
                     "pending_stale_or_insufficient": len(evidence) - assessed_count,
                     "assessed_fraction": assessed_count / len(evidence) if evidence else None},
        "claims": {"total": len(claims), "verified": sum(c.get("status") == "verified" for c in claims.values()),
                   "pending_or_unassessable": sum(c.get("status") in {"draft", "needs_review", "unassessable"}
                                                  for c in claims.values()),
                   "critical_domain_unassessable": sum(d == "unassessable" for d in domain_decisions.values())},
        "denominator_note": "Evidence decisions counted only with available current local sources and named "
                            "supported/contradicted decisions. Pending, insufficient, stale and missing-source "
                            "cases are displayed separately; no semantic correctness score is computed.",
    }
    report["verdict"] = "fail" if report["errors"] else "needs_review" if report["warnings"] or report["unassessable"] else "pass"
    return report


def validate_workspace(root, report_path=None):
    report = validate_state(read_state(root), root)
    if report_path:
        destination = resolve_path(root, report_path)
        protected = {Path(root).resolve() / "state.json", Path(root).resolve() / "events.jsonl"}
        if destination.resolve() in protected:
            raise WorkbenchError("Validation report cannot overwrite state or event history")
        atomic_write(destination, json_bytes(report))
    return report


def _touch(touched, collection, record):
    touched.add(collection + ":" + record["id"])


def _mark_sections(state, section_ids, touched, include_children=False):
    sections = _index(state, "sections")
    selected = set(section_ids)
    if include_children:
        changed = True
        while changed:
            before = len(selected)
            selected.update(section["id"] for section in sections.values() if section.get("parent_id") in selected)
            changed = before != len(selected)
    ancestors = set(selected)
    for sid in list(selected):
        seen = set()
        while sid in sections and sid not in seen:
            seen.add(sid)
            parent = sections[sid].get("parent_id")
            if parent is None:
                break
            ancestors.add(parent)
            sid = parent
    for sid in ancestors:
        section = sections.get(sid)
        if section and section.get("status") == "accepted":
            section["status"] = "needs_review"
            _touch(touched, "sections", section)
    return selected


def _invalidate_claims(state, claim_ids, touched, reason):
    claim_ids = set(claim_ids)
    for claim in state["claims"]:
        if claim["id"] in claim_ids and claim.get("status") not in {"rejected", "unassessable"}:
            claim["status"] = "needs_review"
            _touch(touched, "claims", claim)
    for result in state["check_results"]:
        if result.get("claim_id") in claim_ids:
            result["status"] = "unassessable"
            _touch(touched, "check_results", result)
    section_ids = {s["id"] for s in state["sections"] if set(s.get("claim_ids", [])) & claim_ids}
    for paragraph in state["paragraphs"]:
        if set(paragraph.get("claim_ids", [])) & claim_ids:
            paragraph["status"] = "needs_review"
            _touch(touched, "paragraphs", paragraph)
            section_ids.add(paragraph["section_id"])
    _mark_sections(state, section_ids, touched)
    targets = {("claim", cid) for cid in claim_ids}
    targets.update(("paragraph", p["id"]) for p in state["paragraphs"]
                   if set(p.get("claim_ids", [])) & claim_ids)
    targets.update(("section", sid) for sid in section_ids)
    for review in state["reviews"]:
        if (review.get("target_type"), review.get("target_id")) in targets and review.get("action") == "ACCEPT":
            review["status"] = "open"
            _touch(touched, "reviews", review)


def _invalidate_evidence(state, evidence_ids, touched, reason, reset=True):
    evidence_ids = set(evidence_ids)
    if reset:
        for item in state["evidence"]:
            if item["id"] in evidence_ids:
                verification = item.get("verification", {})
                verification["status"] = "pending"
                verification["note"] = reason
                item["verification"] = verification
                _touch(touched, "evidence", item)
    claims = {claim["id"] for claim in state["claims"]
              if set(claim.get("evidence_ids", [])) & evidence_ids}
    _invalidate_claims(state, claims, touched, reason)


def _invalidate_profile(state, touched, reason, old_profile=None, new_profile=None):
    affected = {result["claim_id"] for result in state["check_results"]}
    for claim in state["claims"]:
        if _applicable_checks(old_profile, claim) or _applicable_checks(new_profile, claim):
            affected.add(claim["id"])
    # Unavailable profiles are treated conservatively: their former scope cannot be reconstructed.
    if old_profile is None and new_profile is None:
        affected.update(claim["id"] for claim in state["claims"] if claim.get("status") == "verified")
    _invalidate_claims(state, affected, touched, reason)


def _refresh_external(state, root, touched):
    for source in state["sources"]:
        fact = _source_facts(root, source)
        evidence_ids = [item["id"] for item in state["evidence"] if item.get("source_id") == source["id"]]
        if fact.get("available") and not fact.get("current"):
            source["sha256"] = fact["digest"]
            _touch(touched, "sources", source)
            _invalidate_evidence(state, evidence_ids, touched, "Local source bytes changed")
        elif not fact.get("available") and any(
                item.get("verification", {}).get("status") == "supported"
                for item in state["evidence"] if item["id"] in evidence_ids):
            _invalidate_evidence(state, evidence_ids, touched, "Local source is unavailable")
    facts = _profile_facts(root, state)
    if facts["configured"] and facts.get("available") and not facts.get("current"):
        state["project"]["domain_profile"]["sha256"] = facts["digest"]
        if facts.get("instructions_digest"):
            state["project"]["domain_profile"]["instructions_sha256"] = facts["instructions_digest"]
        else:
            state["project"]["domain_profile"].pop("instructions_sha256", None)
        touched.add("project:domain_profile")
        _invalidate_profile(state, touched, "Selected domain profile changed", new_profile=facts.get("profile"))
    elif facts["configured"] and not facts.get("available"):
        _invalidate_profile(state, touched, "Selected domain profile is unavailable")


def _external_signature(root, state):
    signatures = {source["id"]: _source_facts(root, source).get("digest") for source in state["sources"]}
    signatures["__profile__"] = _profile_facts(root, state).get("digest")
    signatures["__instructions__"] = _profile_facts(root, state).get("instructions_digest")
    return signatures


def _append_event(root, event):
    with (Path(root) / "events.jsonl").open("ab") as stream:
        stream.write(canonical_bytes(event) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _mutate(root, action, reason, operation, expected_revision=None, artifacts=None):
    root = Path(root).resolve()
    if not _nonempty(reason):
        raise WorkbenchError("A nonempty reason is required")
    with _Lock(root):
        before = read_state(root)
        original_digest = file_hash(root / "state.json")
        if expected_revision is not None and before["revision"] != expected_revision:
            raise ConflictError("Expected revision {}; found {}".format(expected_revision, before["revision"]))
        candidate = copy.deepcopy(before)
        touched = set()
        initial_external = _external_signature(root, candidate)
        _refresh_external(candidate, root, touched)
        details = operation(candidate, touched) or {}
        candidate["revision"] = before["revision"] + 1
        report = validate_state(candidate, root)
        if report["errors"]:
            raise WorkbenchError("Write rejected by integrity checks: " + json.dumps(report["errors"], ensure_ascii=False))
        if file_hash(root / "state.json") != original_digest:
            raise ConflictError("State changed while preparing the write")
        # A new source in the batch is checked by validate_state; existing external files must remain stable.
        final_external = _external_signature(root, before)
        if initial_external != final_external:
            raise ConflictError("External source/profile changed during the write; retry")
        snapshot_name = "revision-{:08d}-{}.json".format(before["revision"], uuid.uuid4().hex[:8])
        atomic_write(root / "snapshots" / snapshot_name, json_bytes(before))
        if artifacts:
            details.update(artifacts(candidate))
        event = {"id": uuid.uuid4().hex, "at": now(), "revision": candidate["revision"],
                 "prior_revision": before["revision"], "action": action, "reason": reason,
                 "touched_ids": sorted(touched), "prior_snapshot": "snapshots/" + snapshot_name,
                 "state_sha256": hashlib.sha256(json_bytes(candidate)).hexdigest(), **details}
        # Persist the transaction event first. Readers can distinguish an incomplete attempt by
        # comparing its revision/checksum with state.json; the state replacement itself is atomic.
        _append_event(root, event)
        atomic_write(root / "state.json", json_bytes(candidate))
        return {"revision": candidate["revision"], "touched_ids": sorted(touched),
                "verdict": report["verdict"], **details}


def init_workspace(root, topic, cutoff=None, language="zh", mode="focused", allow_metadata_only=False,
                   domain_profile=None):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with _Lock(root):
        if (root / "state.json").exists():
            raise WorkbenchError("Workspace already exists; init never overwrites state")
        profile_spec = None
        if domain_profile:
            path = Path(domain_profile).resolve()
            profile = read_json(path)
            errors = _profile_errors(profile) if isinstance(profile, dict) else ["Profile must be an object"]
            if errors:
                raise WorkbenchError("; ".join(errors))
            profile_spec = {"path": str(path), "sha256": file_hash(path)}
            if profile.get("instructions_path"):
                try:
                    profile_spec["instructions_sha256"] = file_hash(resolve_path(path.parent, profile["instructions_path"]))
                except OSError as exc:
                    raise WorkbenchError("Cannot pin linked domain instructions: " + str(exc)) from exc
        state = {"schema_version": SCHEMA, "revision": 0,
                 "project": {"id": uuid.uuid4().hex, "topic": topic, "language": language,
                             "cutoff": cutoff, "mode": mode, "require_fulltext": not allow_metadata_only,
                             "domain_profile": profile_spec}, **{name: [] for name in COLLECTIONS}}
        report = validate_state(state, root)
        if report["errors"]:
            raise WorkbenchError(json.dumps(report["errors"], ensure_ascii=False))
        for directory in ("snapshots", "drafts", "checks"):
            (root / directory).mkdir(exist_ok=True)
        event = {"id": uuid.uuid4().hex, "at": now(), "revision": 0, "action": "init",
                 "reason": "Initialize review workspace", "touched_ids": ["project:" + state["project"]["id"]],
                 "state_sha256": hashlib.sha256(json_bytes(state)).hexdigest()}
        _append_event(root, event)
        atomic_write(root / "state.json", json_bytes(state))
    return {"revision": 0, "root": str(root), "verdict": report["verdict"]}


def put_records(root, collection, records, reason, expected_revision=None):
    if collection not in COLLECTIONS:
        raise WorkbenchError("Unknown collection: " + str(collection))
    batch = copy.deepcopy(records if isinstance(records, list) else [records])
    ids = set()
    for record in batch:
        if not isinstance(record, dict) or not _nonempty(record.get("id")):
            raise WorkbenchError("Each input record needs a nonempty string ID")
        if record["id"] in ids:
            raise WorkbenchError("Duplicate ID within input batch: " + record["id"])
        ids.add(record["id"])

    def operation(state, touched):
        previous = _index(state, collection)
        # Upserts replace one complete record; they never delete another ID.
        for incoming in batch:
            rid = incoming["id"]
            old = previous.get(rid)
            if old == incoming:
                continue
            if old:
                state[collection][state[collection].index(old)] = incoming
            else:
                state[collection].append(incoming)
            _touch(touched, collection, incoming)
            if old and collection == "sources":
                _invalidate_evidence(state, [e["id"] for e in state["evidence"] if e.get("source_id") == rid],
                                     touched, "Source record changed")
            elif old and collection == "evidence":
                material_old = {k: v for k, v in old.items() if k != "verification"}
                material_new = {k: v for k, v in incoming.items() if k != "verification"}
                _invalidate_evidence(state, [rid], touched, "Evidence record changed",
                                     reset=material_old != material_new)
            elif old and collection == "claims":
                requested_status = incoming.get("status")
                if content_hash(old) != content_hash(incoming):
                    _invalidate_claims(state, [rid], touched, "Claim record changed")
                elif old.get("status") != incoming.get("status") and incoming.get("status") != "verified":
                    _invalidate_claims(state, [rid], touched, "Claim verification status changed")
                    # Preserve an explicit rejection/unassessable/draft decision on the edited claim.
                    incoming["status"] = requested_status
            elif old and collection == "sections":
                scope_changed = any(old.get(key) != incoming.get(key) for key in ("paper_ids", "claim_ids", "parent_id"))
                if scope_changed:
                    incoming["status"] = "needs_review"
                    affected = _mark_sections(state, [rid], touched, include_children=True)
                    for paragraph in state["paragraphs"]:
                        if paragraph.get("section_id") in affected:
                            paragraph["status"] = "needs_review"
                            _touch(touched, "paragraphs", paragraph)
            elif old and collection == "paragraphs":
                material_changed = {k: v for k, v in old.items() if k != "status"} != {
                    k: v for k, v in incoming.items() if k != "status"}
                if material_changed:
                    incoming["status"] = "needs_review"
                    _mark_sections(state, [old.get("section_id"), incoming.get("section_id")], touched)
            elif collection == "check_results" and incoming.get("status") != "pass":
                requested_status = incoming.get("status")
                _invalidate_claims(state, [incoming.get("claim_id")], touched, "Domain decision changed")
                incoming["status"] = requested_status
            elif old and collection == "searches":
                dependent = {c["id"] for c in state["claims"] if rid in c.get("search_ids", []) and
                             (c.get("priority_claim") or c.get("absence_claim") or c.get("kind") == "proposed_gap")}
                _invalidate_claims(state, dependent, touched, "Search scope or results changed")
            previous[rid] = incoming
        return {"collection": collection, "input_ids": sorted(ids)}

    return _mutate(root, "put", reason, operation, expected_revision)


def invalidate_source(root, source_id, reason, expected_revision=None):
    def operation(state, touched):
        source = _index(state, "sources").get(source_id)
        if source is None:
            raise WorkbenchError("Unknown source: " + source_id)
        fact = _source_facts(root, source)
        if fact.get("available"):
            source["sha256"] = fact["digest"]
            _touch(touched, "sources", source)
        _invalidate_evidence(state, [e["id"] for e in state["evidence"] if e.get("source_id") == source_id],
                             touched, reason)
        return {"source_id": source_id, "source_available": fact.get("available", False)}
    return _mutate(root, "invalidate", reason, operation, expected_revision)


def review_workspace(root, target, action, reason, reviewer="Codex", expected_revision=None):
    if ":" not in target:
        raise WorkbenchError("Review target must be claim:ID, paragraph:ID or section:ID")
    target_type, target_id = target.split(":", 1)
    if target_type not in TARGET_COLLECTIONS or action not in ENUMS["reviews"]["action"]:
        raise WorkbenchError("Invalid review target/action")

    def operation(state, touched):
        record = _index(state, TARGET_COLLECTIONS[target_type]).get(target_id)
        if record is None:
            raise WorkbenchError("Unknown review target: " + target)
        if action == "ACCEPT":
            record["status"] = "verified" if target_type == "claim" else "accepted"
            _touch(touched, TARGET_COLLECTIONS[target_type], record)
        elif target_type == "claim":
            _invalidate_claims(state, [target_id], touched, reason)
        elif target_type == "paragraph":
            record["status"] = "needs_review"
            _touch(touched, "paragraphs", record)
            _mark_sections(state, [record["section_id"]], touched)
        else:
            record["status"] = "needs_review"
            _touch(touched, "sections", record)
            _mark_sections(state, [target_id], touched)
        if action == "REPLAN_SECTION":
            if target_type == "section":
                scope = {target_id}
            elif target_type == "paragraph":
                scope = {record["section_id"]}
            else:
                scope = {s["id"] for s in state["sections"] if target_id in s.get("claim_ids", [])}
                scope.update(p["section_id"] for p in state["paragraphs"] if target_id in p.get("claim_ids", []))
            scope = _mark_sections(state, scope, touched, include_children=True)
            for section in state["sections"]:
                if section["id"] in scope:
                    section["status"] = "needs_review"
                    _touch(touched, "sections", section)
            for paragraph in state["paragraphs"]:
                if paragraph.get("section_id") in scope:
                    paragraph["status"] = "needs_review"
                    _touch(touched, "paragraphs", paragraph)
        elif action == "REPLAN_PARAGRAPH" and target_type == "section":
            for paragraph in state["paragraphs"]:
                if paragraph.get("section_id") == target_id:
                    paragraph["status"] = "needs_review"
                    _touch(touched, "paragraphs", paragraph)
        review = {"id": "review-" + uuid.uuid4().hex, "target_type": target_type, "target_id": target_id,
                  "action": action, "reason": reason, "reviewer": reviewer,
                  "status": "resolved" if action == "ACCEPT" else "open"}
        state["reviews"].append(review)
        _touch(touched, "reviews", review)
        return {"review_id": review["id"], "target": target}
    return _mutate(root, "review", reason, operation, expected_revision)


def configure_workspace(root, domain_profile=_UNSET, reason=None, expected_revision=None, project_updates=None):
    if project_updates is not None:
        if not isinstance(project_updates, dict) or not project_updates:
            raise WorkbenchError("Project updates must be a nonempty object")
        unknown = set(project_updates) - PROJECT_FIELDS
        if unknown:
            raise WorkbenchError("Protected or unknown project fields: " + ", ".join(sorted(unknown)))
    path = Path(domain_profile).resolve() if domain_profile is not _UNSET and domain_profile else None
    new_profile = read_json(path) if path else None
    if new_profile is not None:
        errors = _profile_errors(new_profile) if isinstance(new_profile, dict) else ["Profile must be an object"]
        if errors:
            raise WorkbenchError("; ".join(errors))
    spec = {"path": str(path), "sha256": file_hash(path)} if path else None
    if new_profile and new_profile.get("instructions_path"):
        try:
            spec["instructions_sha256"] = file_hash(resolve_path(path.parent, new_profile["instructions_path"]))
        except OSError as exc:
            raise WorkbenchError("Cannot pin linked domain instructions: " + str(exc)) from exc

    def operation(state, touched):
        old_facts = _profile_facts(root, state)
        if domain_profile is not _UNSET and state["project"].get("domain_profile") != spec:
            state["project"]["domain_profile"] = spec
            touched.add("project:domain_profile")
            _invalidate_profile(state, touched, reason, old_profile=old_facts.get("profile"), new_profile=new_profile)
        changed_fields = []
        for key, value in (project_updates or {}).items():
            if state["project"].get(key) != value:
                state["project"][key] = copy.deepcopy(value)
                touched.add("project:" + key)
                changed_fields.append(key)
        if set(changed_fields) & {"topic", "cutoff", "research_questions", "questions", "inclusion_criteria", "criteria", "exclusions"}:
            dependent = {c["id"] for c in state["claims"] if c.get("priority_claim") or c.get("absence_claim") or c.get("kind") == "proposed_gap"}
            _invalidate_claims(state, dependent, touched, "Project search scope changed")
        return {"domain_profile": state["project"].get("domain_profile"), "project_fields_changed": sorted(changed_fields)}
    return _mutate(root, "configure", reason, operation, expected_revision)


def checkpoint_workspace(root, label, expected_revision=None):
    if not _nonempty(label):
        raise WorkbenchError("Checkpoint label cannot be empty")
    safe_label = re.sub(r"[^\w.-]+", "_", label, flags=re.UNICODE).strip("._")[:80] or "checkpoint"
    def artifacts(state):
        payload = json_bytes(state)
        name = "checkpoint-{}-r{:08d}-{}".format(safe_label, state["revision"], uuid.uuid4().hex[:8])
        destination = Path(root) / "snapshots" / (name + ".json")
        atomic_write(destination, payload)
        manifest = {"schema_version": "literature-checkpoint/1", "label": label,
                    "at": now(), "revision": state["revision"], "state_file": destination.name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "limitation": "External source files are not frozen by a checkpoint."}
        atomic_write(destination.with_suffix(".manifest.json"), json_bytes(manifest))
        return {"checkpoint": str(destination.resolve()), "manifest": str(destination.with_suffix(".manifest.json").resolve()),
                "checkpoint_revision": state["revision"], "sha256": manifest["sha256"]}
    return _mutate(root, "checkpoint", "Checkpoint: " + label,
                   lambda state, touched: {"label": label}, expected_revision, artifacts=artifacts)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--topic", required=True)
    init.add_argument("--cutoff")
    init.add_argument("--language", default="zh")
    init.add_argument("--mode", default="focused", choices=("focused", "comprehensive", "systematic-prep"))
    init.add_argument("--allow-metadata-only", action="store_true")
    init.add_argument("--domain-profile")
    put = commands.add_parser("put")
    put.add_argument("--collection", required=True, choices=COLLECTIONS)
    put.add_argument("--input", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--report")
    invalidate = commands.add_parser("invalidate")
    invalidate.add_argument("--source", required=True)
    review = commands.add_parser("review")
    review.add_argument("--target", required=True)
    review.add_argument("--action", required=True, choices=sorted(ENUMS["reviews"]["action"]))
    review.add_argument("--reviewer", default="Codex")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--label", required=True)
    configure = commands.add_parser("configure")
    profile_group = configure.add_mutually_exclusive_group(required=True)
    profile_group.add_argument("--domain-profile")
    profile_group.add_argument("--clear-domain-profile", action="store_true")
    profile_group.add_argument("--project")
    for command in (put, validate, invalidate, review, checkpoint, configure):
        command.add_argument("--root", required=True)
    for command in (put, invalidate, review, configure):
        command.add_argument("--reason", required=True)
    for command in (put, invalidate, review, checkpoint, configure):
        command.add_argument("--expected-revision", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_workspace(args.root, args.topic, args.cutoff, args.language, args.mode,
                                    args.allow_metadata_only, args.domain_profile)
        elif args.command == "put":
            result = put_records(args.root, args.collection, read_json(args.input), args.reason, args.expected_revision)
        elif args.command == "validate":
            result = validate_workspace(args.root, args.report)
        elif args.command == "invalidate":
            result = invalidate_source(args.root, args.source, args.reason, args.expected_revision)
        elif args.command == "review":
            result = review_workspace(args.root, args.target, args.action, args.reason, args.reviewer, args.expected_revision)
        elif args.command == "configure":
            result = configure_workspace(args.root, _UNSET if args.project else args.domain_profile,
                                         args.reason, args.expected_revision,
                                         read_json(args.project) if args.project else None)
        else:
            result = checkpoint_workspace(args.root, args.label, args.expected_revision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == "validate" and result["verdict"] == "fail" else 0
    except (WorkbenchError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 3 if isinstance(exc, ConflictError) else 1


if __name__ == "__main__":
    sys.exit(main())
