"""Reading-copy figure identities and local artwork; never fetches or runs detection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _text(element, tags):
    for child in element.iter():
        if _local(child.tag) in tags:
            def content(node):
                parts = [node.text or '']
                for nested in node:
                    text = content(nested)
                    if _local(nested.tag) in ('title', 'p', 'simple-para'):
                        text = '\n\n' + text + '\n\n'
                    parts.extend([text, nested.tail or ''])
                return ''.join(parts)
            return '\n\n'.join(re.sub(r'\s+', ' ', p).strip()
                               for p in content(child).split('\n\n') if p.strip())
    return ''


def _safe_file(root, name):
    try:
        if not name or urlsplit(name).scheme or name.startswith('//'):
            return None
    except ValueError:
        return None  # Malformed URI is not a local artwork reference.
    path = (root / unquote(name)).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    return path if path.is_file() else None


def figure_dependencies(root: Path):
    """Bounded to this paper and its known artwork folders (not a corpus walk)."""
    folders = [root, root/'pmc_figures', root/'publisher_figures']
    folders.extend(p for p in root.glob('*_figures') if p.is_dir())
    paths = set()
    for folder in folders:
        if folder.is_dir() and folder.resolve().is_relative_to(root.resolve()):
            paths.update(p for p in folder.iterdir() if p.is_file())
    # Include nested XML-relative artwork and missing candidates so arrivals and
    # changes invalidate the reading copy even outside conventional folders.
    for xml in root.glob('*.xml'):
        try:
            for el in ET.parse(xml).getroot().iter():
                if _local(el.tag) in ('graphic', 'inline-graphic', 'link'):
                    for k, value in el.attrib.items():
                        if _local(k) in ('href', 'locator'):
                            candidate = (root/unquote(value)).resolve()
                            if candidate.is_relative_to(root.resolve()):
                                paths.add(candidate)
        except (OSError, ET.ParseError, ValueError):
            pass  # The renderer reports unreadable XML; this is only a cache key.
    def stamp(p):
        try:
            s = p.stat()
            return str(p), s.st_size, s.st_mtime_ns, s.st_ctime_ns
        except OSError:
            return str(p), None, None, None
    return tuple(stamp(p) for p in sorted(paths))


def xml_figures(xml: Path, *, paper_dir: Path | None = None, archived_assets=None):
    """Full XML captions plus safe media references; archived assets are explicit.

    Asset records contain name, ref and availability, already hash-validated by
    the workbench. Never search the object-store directory beside archived XML.
    """
    root = ET.parse(xml).getroot()
    manifests = []
    if paper_dir is not None:
        for folder in ('pmc_figures', 'publisher_figures'):
            if not (paper_dir/folder).resolve().is_relative_to(paper_dir.resolve()):
                continue
            try:
                rows = json.loads((paper_dir/folder/'manifest.json').read_text()).get('figures', [])
                manifests.extend((folder, row) for row in rows if isinstance(row, dict))
            except (OSError, ValueError, AttributeError):
                continue  # A bad manifest cannot license a figure/image association.
    figures = []
    for el in root.iter():
        if _local(el.tag) not in ('fig', 'figure'):
            continue
        fid = el.get('id') or ''
        label = _text(el, ('label',)) or f'Figure {len(figures)+1}'
        caption = _text(el, ('caption', 'simple-para'))
        refs = []
        for child in el.iter():
            if _local(child.tag) in ('graphic', 'link'):
                for k, value in child.attrib.items():
                    if _local(k) in ('href', 'locator') and value not in refs:
                        refs.append(value)
        graphics = []
        for reference in refs or ['']:
            candidates = {}
            failed = []
            archived_matches = [a for a in archived_assets or [] if reference and
                                (a['name'] == reference or Path(a['name']).name == Path(reference).name)]
            if archived_matches:
                if len(archived_matches) > 1:
                    failed.append('Ambiguous archived image reference')
                elif archived_matches[0]['availability'] == 'verified':
                    candidates[archived_matches[0]['ref']] = 'verified'
                else:
                    failed.append('Archived image unavailable or changed')
            elif paper_dir is not None:
                direct = _safe_file(paper_dir, reference)
                if direct:
                    candidates[direct.relative_to(paper_dir.resolve()).as_posix()] = 'available'
                for folder, row in manifests:
                    # Exact source ID or graphic reference; normalized labels are
                    # intentionally not evidence of identity (Extended Data collides).
                    row_ref = row.get('href') or row.get('locator')
                    matched = (reference and row_ref == reference) or (
                        fid and row.get('id') == fid and (len(refs) <= 1 or row_ref == reference))
                    if not matched:
                        continue
                    file = _safe_file(paper_dir, f"{folder}/{row.get('file') or ''}")
                    if file is None:
                        failed.append('Image unavailable on this computer')
                        continue
                    sha = row.get('sha256')
                    try:
                        valid = not sha or hashlib.sha256(file.read_bytes()).hexdigest() == sha
                    except OSError:
                        failed.append('Image could not be read on this computer')
                        continue
                    if not valid:
                        failed.append('Image changed since its manifest was recorded')
                        continue
                    candidates[file.relative_to(paper_dir.resolve()).as_posix()] = 'available'
            # Multiple explicit renditions may all be displayed; their association
            # is proven by the XML reference, not a guessed largest-picture rule.
            if candidates:
                graphics.extend({'reference': reference, 'relpath': ref, 'status': ('local_current' if archived_assets is not None and status == 'available' else status)}
                                for ref, status in candidates.items())
            else:
                graphics.append({'reference': reference, 'relpath': None,
                                 'status': failed[0] if failed else 'Image unavailable on this computer'})
        figures.append({'id': fid, 'anchor': f'xml-figure-{len(figures)+1}',
                        'label': label, 'caption': caption, 'graphics': graphics})
    return figures
