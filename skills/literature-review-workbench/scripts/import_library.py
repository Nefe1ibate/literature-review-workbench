#!/usr/bin/env python3
"""Read-only, standard-library adapters for a maintained literature library."""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

COLLECTIONS = ('papers', 'sources', 'evidence', 'searches', 'claims', 'sections',
               'paragraphs', 'reviews', 'check_results')
PAPER_STATUSES = {'candidate', 'included', 'excluded', 'pending'}
READ_STATUSES = {'unread', 'metadata_only', 'partial', 'full'}


class ImportErrorWithContext(ValueError):
    pass


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def stable_id(prefix, value):
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return prefix + '-' + hashlib.sha256(blob).hexdigest()[:16]


def get_field(record, path, default=None):
    current = record
    if not path:
        return current
    for key in path.split('.'):
        if isinstance(current, dict):
            if key not in current:
                return default
            current = current[key]
        elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            return default
    return current


def set_field(record, path, value):
    keys = path.split('.')
    current = record
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        if not isinstance(current[key], dict):
            raise ImportErrorWithContext('Overlapping mapping target: ' + path)
        current = current[key]
    current[keys[-1]] = value


def mapped_record(raw, mapping):
    if mapping is None:
        return dict(raw)
    out = {}
    for target, spec in mapping.items():
        if isinstance(spec, str):
            value = get_field(raw, spec)
        elif isinstance(spec, list):
            value = next((get_field(raw, key) for key in spec
                          if get_field(raw, key) not in (None, '')), None)
        elif isinstance(spec, dict) and 'constant' in spec:
            value = spec['constant']
        else:
            raise ImportErrorWithContext('Invalid field mapping: ' + target)
        if value is not None:
            set_field(out, target, value)
    return out


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ImportErrorWithContext(str(path) + ': ' + str(exc)) from exc


def load_records(path, fmt=None, records_key=None):
    fmt = fmt or path.suffix.lstrip('.').lower()
    if not path.is_file():
        raise ImportErrorWithContext('Required ledger is missing: ' + str(path))
    if fmt == 'json':
        data = load_json(path)
        if records_key:
            data = get_field(data, records_key)
        if isinstance(data, dict):
            data = [data]
    elif fmt == 'jsonl':
        data = []
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if line.strip():
                try:
                    data.append(json.loads(line))
                except ValueError as exc:
                    raise ImportErrorWithContext(f'{path}:{number}: {exc}') from exc
    elif fmt == 'csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            data = list(csv.DictReader(stream))
    else:
        raise ImportErrorWithContext('Supported ledger formats: json, jsonl, csv')
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ImportErrorWithContext('Ledger must contain an array of objects: ' + str(path))
    return data


def normalize_doi(value):
    text = str(value or '').strip().lower()
    return re.sub(r'^(https?://(dx\.)?doi\.org/|doi:\s*)', '', text)


def authors_list(value):
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    # Do not split commas: they are part of "surname, given name".
    return [part.strip() for part in re.split(r'\s+and\s+|;', str(value)) if part.strip()]


def existing_locator(raw):
    loc = dict(raw.get('locator')) if isinstance(raw.get('locator'), dict) else {}
    aliases = {'printed_page': ('printed_page', 'printed_pages', 'print_pages',
                                'author_printed_pages', 'author_print_pages',
                                'published_print_pages', 'journal_pages', 'page_labels'),
               'section': ('section', 'locator', 'location', 'locators'),
               'equation': ('equation',), 'table': ('table',),
               'proposition': ('proposition',), 'anchor': ('anchor',)}
    pages = raw.get('pdf_page', raw.get('pdf_pages', raw.get('author_pdf_pages')))
    if isinstance(pages, int) and not isinstance(pages, bool):
        loc.setdefault('pdf_page', pages)
    elif isinstance(pages, list) and pages:
        first = pages[0]
        if isinstance(first, int) and not isinstance(first, bool):
            loc.setdefault('pdf_page', first)
    elif isinstance(pages, str):
        first = re.match(r'^\s*(\d+)', pages)
        if first:
            loc.setdefault('pdf_page', int(first.group(1)))
    for target, names in aliases.items():
        if target not in loc:
            val = next((raw[name] for name in names if raw.get(name)), None)
            if isinstance(val, dict):
                continue
            if val is not None:
                loc[target] = ', '.join(map(str, val)) if isinstance(val, list) else str(val)
    return loc


class Importer:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.config = load_json(self.config_path)
        if self.config.get('schema_version') != 'literature-library-config/1':
            raise ImportErrorWithContext('Unsupported library config schema_version')
        self.base = self.config_path.parent
        self.root = self.config_path_value(self.config.get('library_root', '.'))
        if not self.root.is_dir():
            raise ImportErrorWithContext('Library root is missing: ' + str(self.root))
        self.bundle = {'schema_version': 'literature-library-bundle/1',
                       **{name: [] for name in COLLECTIONS}}
        self.warnings = []
        self.aliases = {}
        self.dois = {}
        self.paper_by_id = {}
        self.source_by_id = {}
        self.input_files = {}

    def config_path_value(self, value):
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.base / path).resolve()

    def data_path(self, value):
        if value in (None, ''):
            return None
        path = Path(value).expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    def remember_input(self, path):
        self.input_files[str(path)] = digest_file(path)

    def ext(self, item, history):
        item.setdefault('extensions', {})['library_import'] = history

    def add_paper(self, raw, history=None):
        item = dict(raw)
        title = str(item.get('title') or '').strip()
        if not title:
            raise ImportErrorWithContext('Paper title is required')
        item['title'] = title
        item['authors'] = authors_list(item.get('authors', item.get('author')))
        if item.get('year') not in (None, ''):
            try:
                item['year'] = int(item['year'])
            except (TypeError, ValueError):
                raise ImportErrorWithContext('Invalid year for ' + title)
        doi = normalize_doi(item.get('doi'))
        if doi:
            item['doi'] = doi
        else:
            item.pop('doi', None)
        key = doi or [title.casefold(), item['authors'], item.get('year')]
        original_id = str(item.get('id') or stable_id('paper', key))
        item['id'] = self.dois.get(doi, original_id) if doi else original_id
        item['status'] = item.get('status', 'candidate')
        if item['status'] not in PAPER_STATUSES:
            self.warnings.append('Unknown paper status retained in import history: ' + original_id)
            item['status'] = 'pending'
        read_status = item.get('read_status', 'metadata_only')
        if read_status not in READ_STATUSES:
            read_status = 'partial' if item.get('reading_scope') else 'metadata_only'
        if read_status == 'full' and not item.get('reading_scope'):
            self.warnings.append('Full reading without explicit scope demoted: ' + original_id)
            read_status = 'partial'
        item['read_status'] = read_status
        self.ext(item, history or {'record_id': original_id, 'historic_read_status': raw.get('read_status'),
                                 'historic_status': raw.get('status')})
        self.aliases[original_id] = item['id']
        if item['id'] in self.paper_by_id:
            old = self.paper_by_id[item['id']]
            if not doi and old['title'].casefold() != title.casefold():
                raise ImportErrorWithContext('Conflicting paper ID without DOI: ' + original_id)
            hist = old['extensions']['library_import']
            hist.setdefault('aliases', []).append(original_id)
            if old['title'].casefold() != title.casefold() or old.get('year') != item.get('year'):
                self.warnings.append('DOI metadata conflict retained: ' + doi)
                hist.setdefault('identity_conflicts', []).append(item)
            return old
        self.bundle['papers'].append(item)
        self.paper_by_id[item['id']] = item
        if doi:
            self.dois[doi] = item['id']
        return item

    def add_source(self, raw):
        item = dict(raw)
        item['paper_id'] = self.aliases.get(str(item.get('paper_id')), str(item.get('paper_id')))
        if item['paper_id'] not in self.paper_by_id:
            raise ImportErrorWithContext('Source references unknown paper: ' + item['paper_id'])
        path = self.data_path(item.get('path'))
        item['path'] = str(path) if path else None
        historic_sha = item.get('sha256')
        item['sha256'] = digest_file(path) if path and path.is_file() else None
        if path and not path.is_file():
            self.warnings.append('Local source unavailable: ' + str(path))
        if historic_sha and item['sha256'] and historic_sha != item['sha256']:
            self.warnings.append('Source bytes differ from historic digest: ' + str(path))
        item['kind'] = item.get('kind') or ('pdf' if path and path.suffix.lower() == '.pdf' else
                                          'html' if path and path.suffix.lower() in ('.html', '.htm') else
                                          'text' if path and path.suffix.lower() in ('.txt', '.md') else 'other')
        item['version_label'] = str(item.get('version_label') or (path.name if path else 'unavailable historic source'))
        item['id'] = str(item.get('id') or stable_id('source', [item['paper_id'], item['path'],
                                                              item['version_label'], item.get('source_url')]))
        if item.get('page_count') not in (None, ''):
            item['page_count'] = int(item['page_count'])
        history = dict(item.get('extensions', {}).get('library_import', {}))
        history.update({'historic_sha256': historic_sha,
                        'availability': 'local' if item['sha256'] else 'unavailable'})
        self.ext(item, history)
        if item['id'] in self.source_by_id:
            if self.source_by_id[item['id']] != item:
                raise ImportErrorWithContext('Conflicting source ID: ' + item['id'])
            return self.source_by_id[item['id']]
        self.bundle['sources'].append(item)
        self.source_by_id[item['id']] = item
        return item

    def add_evidence(self, raw):
        item = dict(raw)
        item['paper_id'] = self.aliases.get(str(item.get('paper_id')), str(item.get('paper_id')))
        item['id'] = str(item.get('id') or stable_id('evidence', item))
        original = item.get('verification')
        item['verification'] = {'status': 'pending', 'note': 'Imported historical evidence; compare with source before reuse.'}
        self.ext(item, {**item.get('extensions', {}).get('library_import', {}),
                        'historic_verification': original})
        item.setdefault('locator', {})
        self.bundle['evidence'].append(item)
        return item

    def add_claim(self, raw):
        item = dict(raw)
        item['id'] = str(item.get('id') or stable_id('claim', item))
        original = item.get('status')
        item['status'] = 'needs_review'
        item.setdefault('kind', 'source_result')
        item.setdefault('evidence_ids', [])
        self.ext(item, {**item.get('extensions', {}).get('library_import', {}), 'historic_status': original})
        self.bundle['claims'].append(item)
        return item

    def mapped(self):
        collections = self.config.get('collections')
        if not isinstance(collections, dict) or 'papers' not in collections:
            raise ImportErrorWithContext('mapped-ledger requires collections.papers')
        unknown = set(collections) - set(COLLECTIONS)
        if unknown:
            raise ImportErrorWithContext('Unknown collections: ' + ', '.join(sorted(unknown)))
        for name in COLLECTIONS:
            if name not in collections:
                continue
            spec = collections[name]
            path = self.config_path_value(spec['path'])
            raw_records = load_records(path, spec.get('format'), spec.get('records_key'))
            self.remember_input(path)
            for raw in raw_records:
                item = mapped_record(raw, spec.get('mapping'))
                if name == 'papers':
                    self.add_paper(item)
                elif name == 'sources':
                    self.add_source(item)
                elif name == 'evidence':
                    self.add_evidence(item)
                elif name == 'claims':
                    self.add_claim(item)
                else:
                    # Imported acceptances and domain judgements are never current.
                    if name in ('sections', 'paragraphs'):
                        item['status'] = 'needs_review'
                    elif name == 'reviews':
                        item['status'] = 'unassessable'
                    elif name == 'check_results':
                        item['status'] = 'unassessable'
                    if 'paper_ids' in item:
                        item['paper_ids'] = [self.aliases.get(str(k), str(k)) for k in item['paper_ids']]
                    self.ext(item, {'historic_record': raw})
                    self.bundle[name].append(item)

    def legacy_reading(self, data):
        scope = next((data[k] for k in ('full_read', 'reading', 'fulltext', 'reading_completeness', 'read_pages', 'read_page_ranges')
                      if data.get(k)), None)
        explicit_full = bool(data.get('read_complete') is True or
                             get_field(data, 'full_read.completed') is True or
                             get_field(data, 'fulltext.status') == 'downloaded_full_text_read')
        # Unstructured human claims remain historical, not inferred completion.
        return ('full' if explicit_full and scope else 'partial' if scope else 'metadata_only'), scope

    def reading_report_library(self):
        spec = self.config.get('reading_report', {})
        ledger_path = self.config_path_value(spec.get('papers_path', 'evidence/reading_status.json'))
        source_path = self.config_path_value(spec.get('sources_path', 'evidence/source_manifest.json'))
        papers = load_records(ledger_path)
        manifests = load_records(source_path)
        self.remember_input(ledger_path)
        self.remember_input(source_path)
        details = {}
        for row in papers:
            details_path = self.data_path(row.get('evidence_file'))
            data = {}
            if details_path and details_path.is_file():
                data = load_json(details_path)
                self.remember_input(details_path)
            elif details_path:
                self.warnings.append('Reading details unavailable: ' + str(details_path))
            bib = data.get('bibliography', {})
            read_status, scope = self.legacy_reading(data)
            inclusion = data.get('inclusion', {})
            item = {k: bib.get(k, row.get(k)) for k in ('title', 'authors', 'year', 'doi') if bib.get(k, row.get(k)) is not None}
            item['id'] = str(row.get('id') or data.get('key') or data.get('paper_id'))
            item['status'] = 'included' if row.get('formal_review_inclusion') is True or inclusion.get('decision') == 'include' else 'candidate'
            item['read_status'] = read_status
            if scope:
                item['reading_scope'] = scope
            item['missing_parts'] = data.get('missing_scope', data.get('missing_materials', []))
            item['decision_reason'] = data.get('inclusion_reason') or inclusion.get('rubric') or 'Historical library decision; re-evaluate for the new question.'
            paper = self.add_paper(item, {'record_id': row.get('id'), 'historic_read_status': row.get('read_status'),
                                         'historic_read_details': scope, 'detail_path': str(details_path) if details_path else None,
                                         'historic_inclusion': row.get('formal_review_inclusion'),
                                         'report_path': row.get('report_source'), 'report_pdf': row.get('report_pdf')})
            details[paper['id']] = data
        for row in manifests:
            pid = self.aliases.get(str(row.get('paper_id')), str(row.get('paper_id')))
            if pid not in self.paper_by_id:
                self.warnings.append('Manifest source for unlisted paper omitted: ' + pid)
                continue
            source = self.add_source({'paper_id': pid, 'path': row.get('path'),
                                      'sha256': row.get('sha256'), 'page_count': row.get('pages'),
                                      'accessed_at': row.get('acquisition_record_date'),
                                      'extensions': {'library_import': {'manifest_record': row}}})
            data = details.get(pid, {})
            candidates = data.get('sources', [])
            if not isinstance(candidates, list):
                candidates = []
            for metadata in candidates:
                if self.data_path(metadata.get('path')) == self.data_path(source['path']):
                    source['source_url'] = metadata.get('source_url')
                    source['version_label'] = str(metadata.get('version') or source['version_label'])
                    source['extensions']['library_import']['source_alias'] = metadata.get('id')
            for key in ('version', 'supplement', 'provenance'):
                meta = data.get(key, {})
                if not isinstance(meta, dict):
                    continue
                known_sha = meta.get('sha256') or (meta.get('article_sha256') if key == 'provenance' else None)
                known_path = meta.get('local_pdf') or meta.get('article_path')
                if (known_sha and known_sha == source['sha256']) or (known_path and self.data_path(known_path) == self.data_path(source['path'])):
                    source['source_url'] = meta.get('source_url') or meta.get('article_source_url')
                    source['version_label'] = str(meta.get('status') or meta.get('version') or source['version_label'])
                    source['extensions']['library_import']['source_alias'] = 'supplement' if key == 'supplement' else 'article'
            main = self.data_path(get_field(data, 'provenance.article_path') or get_field(data, 'provenance.local_pdf'))
            version_sha = get_field(data, 'version.sha256')
            if (main and source['path'] == str(main)) or (version_sha and source['sha256'] == version_sha):
                self.paper_by_id[pid]['primary_source_id'] = source['id']
        for pid, data in details.items():
            self.import_legacy_claims(pid, data)

    def choose_source(self, pid, claim, data):
        available = [s for s in self.bundle['sources'] if s['paper_id'] == pid]
        token = claim.get('source_file', claim.get('document', claim.get('source')))
        explicit_path = self.data_path(token) if isinstance(token, str) and ('.' in token or '/' in token or '\\' in token) else None
        if explicit_path:
            matches = [s for s in available if s['path'] == str(explicit_path) or Path(s['path'] or '').name == Path(token).name]
            if len(matches) == 1:
                return matches[0]
        aliases = {'main': 'article', 'published': 'article', 'supp': 'supplement'}
        wanted = aliases.get(str(token), str(token)) if token else 'article'
        matches = [s for s in available if aliases.get(
            str(s.get('extensions', {}).get('library_import', {}).get('source_alias')),
            str(s.get('extensions', {}).get('library_import', {}).get('source_alias'))) == wanted]
        if len(matches) == 1:
            return matches[0]
        primary_id = self.paper_by_id[pid].get('primary_source_id')
        if not token and primary_id:
            return self.source_by_id[primary_id]
        if not token and len(available) == 1:
            return available[0]
        # No title/filename-based guess at an ambiguous pagination or version.
        sid = stable_id('source-unresolved', [pid, token or 'unspecified'])
        if sid not in self.source_by_id:
            self.warnings.append('Source association needs review: ' + pid + ' / ' + str(token or 'unspecified'))
            self.add_source({'id': sid, 'paper_id': pid, 'path': None, 'kind': 'pdf',
                             'version_label': 'Unresolved historical source: ' + str(token or 'unspecified'),
                             'extensions': {'library_import': {'unresolved_source_token': token}}})
        return self.source_by_id[sid]

    def import_legacy_claims(self, pid, data):
        claims = next((data[key] for key in ('exact_page_claims', 'claims', 'key_claims', 'evidence') if data.get(key)), [])
        if isinstance(claims, dict):
            claims = [claims]
        for index, raw in enumerate(claims, 1):
            text = raw.get('claim') or raw.get('text_zh') or raw.get('text')
            if not text:
                self.warnings.append('Historical item without claim text omitted: ' + pid)
                continue
            cid = pid + ':' + str(raw.get('id') or raw.get('claim_id') or f'claim-{index}')
            source = self.choose_source(pid, raw, data)
            locator = existing_locator(raw)
            eid = cid + ':evidence'
            evidence = {'id': eid, 'paper_id': pid, 'source_id': source['id'],
                        'locator': locator, 'paraphrase': str(text),
                        'extensions': {'library_import': {'historic_record': raw}}}
            if raw.get('quote'):
                evidence['excerpt'] = raw['quote']
            if not locator:
                self.warnings.append('Historical evidence lacks a precise locator: ' + eid)
            self.add_evidence(evidence)
            self.add_claim({'id': cid, 'text': str(text), 'kind': 'source_result', 'evidence_ids': [eid],
                            'extensions': {'library_import': {'historic_claim_type': raw.get('claim_type')}}})

    def run(self, output_path):
        output = Path(output_path).resolve()
        if output == self.root or self.root in output.parents:
            raise ImportErrorWithContext('Output must be outside the connected library root: ' + str(self.root))
        adapter = self.config.get('adapter')
        if adapter == 'mapped-ledger':
            self.mapped()
        elif adapter == 'reading-report-library':
            self.reading_report_library()
        else:
            raise ImportErrorWithContext('Unknown adapter: ' + str(adapter))
        for collection in COLLECTIONS:
            identifiers = [str(item.get('id', '')) for item in self.bundle[collection]]
            if any(not identifier for identifier in identifiers) or len(identifiers) != len(set(identifiers)):
                raise ImportErrorWithContext('Missing or duplicate IDs in ' + collection)
        # The engine imports papers before sources. Preserve the preferred version
        # as provenance so the first paper batch has no forward foreign key.
        for paper in self.bundle['papers']:
            if paper.get('primary_source_id'):
                paper['extensions']['library_import']['historic_primary_source_id'] = paper.pop('primary_source_id')
        self.bundle['import_metadata'] = {'library_root': str(self.root), 'adapter': adapter,
                                         'config_path': str(self.config_path),
                                         'config_sha256': digest_file(self.config_path),
                                         'imported_at': datetime.now(timezone.utc).isoformat(),
                                         'input_fingerprints': self.input_files,
                                         'paper_id_aliases': self.aliases, 'warnings': self.warnings,
                                         'verification_policy': 'Historical evidence pending; claims need revalidation.'}
        output.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                             prefix=output.name + '.', suffix='.tmp', delete=False) as stream:
                temp_name = stream.name
                json.dump(self.bundle, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, output)
        finally:
            if temp_name and Path(temp_name).exists():
                Path(temp_name).unlink()
        return self.bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        bundle = Importer(args.config).run(args.output)
    except (ImportErrorWithContext, OSError, TypeError, KeyError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({'status': 'imported', 'output': str(Path(args.output).resolve()),
                      'counts': {key: len(bundle[key]) for key in COLLECTIONS},
                      'warnings': bundle['import_metadata']['warnings']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
