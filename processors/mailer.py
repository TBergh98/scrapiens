"""Email digest builder for grant keyword matches.

This module reads the latest grants_by_keywords_emails_*.json produced by
GrantEmailMatcher, groups matches by recipient email, renders HTML/plaintext
bodies via Jinja2 templates, and saves a per-run digest file in
intermediate_outputs/ without sending any email.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dateutil import parser as date_parser
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from config import get_config
from config.settings import Config
from utils.file_utils import ensure_directory, load_json, save_json
from utils.logger import get_logger

logger = get_logger(__name__)


class DigestBuilder:
    """Builds email-ready digests grouped by recipient."""

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        base_dir: Optional[Path] = None,
        config: Optional[Config] = None,
        current_date: Optional[date] = None,
    ) -> None:
        self.config = config or get_config()
        self.base_dir = Path(base_dir) if base_dir else self.config.get_path('paths.base_dir')
        self.template_dir = Path(template_dir) if template_dir else (self.base_dir / "templates")
        self.current_date = current_date or datetime.now().date()

        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )

    def find_latest_source(self, directory: Optional[Path] = None) -> Path:
        """Return the most recent grants_by_keywords_emails_*.json by timestamp in filename."""
        dir_path = Path(directory) if directory else self.config.get_full_path('paths.output_match_keywords_dir')
        candidates = list(dir_path.glob("grants_by_keywords_emails_*.json"))
        if not candidates:
            raise FileNotFoundError(
                f"No grants_by_keywords_emails_*.json files found in {dir_path}")

        def _ts_from_name(path: Path) -> datetime:
            stem = path.stem  # grants_by_keywords_emails_YYYYMMDD_HHMMSS
            parts = stem.split("_")
            ts = "".join(parts[-2:]) if len(parts) >= 2 else ""
            try:
                return datetime.strptime(ts, "%Y%m%d%H%M%S")
            except Exception:
                return datetime.fromtimestamp(path.stat().st_mtime)

        latest = max(candidates, key=_ts_from_name)
        return latest

    def build_digests(
        self,
        source_path: Path,
        output_path: Optional[Path] = None,
        apply_deadline_filter: bool = False
    ) -> Dict[str, Any]:
        """
        Load matches, group by recipient, render bodies, and write digest JSON.
        
        Args:
            source_path: Path to grants_by_keywords_emails_*.json
            output_path: Path to save digests. If None, auto-generates timestamp.
            apply_deadline_filter: If True, filter grants by deadline cutoff (legacy behavior).
                                   If False (default), include all grants from source.
        """
        source_path = Path(source_path)
        data = load_json(source_path)
        if not isinstance(data, dict) or 'results' not in data:
            raise ValueError("Input file must contain a top-level 'results' list")

        # Apply deadline filtering only if explicitly enabled
        if apply_deadline_filter:
            original_count = len(data['results'])
            deadline_filter_days = self.config.get('email.deadline_filter_days', 30)
            data['results'] = self._filter_by_deadline(data['results'], days_back=deadline_filter_days)
            filtered_count = len(data['results'])
            cutoff_date = (self.current_date - timedelta(days=deadline_filter_days)).isoformat()
            logger.info(
                f"Deadline filtering: kept {filtered_count}/{original_count} grants "
                f"(cutoff: {cutoff_date}, filter_days: {deadline_filter_days})"
            )
        else:
            logger.info(
                f"Deadline filtering disabled: including all {len(data['results'])} grants from source "
                f"(filtering should be handled in match-keywords step)"
            )

        grouped = self._group_by_email(data['results'])
        if not grouped:
            logger.warning("No matched emails found in source data; digest will be empty")

        digests: List[Dict[str, Any]] = []
        total_grants = 0

        for email in sorted(grouped.keys()):
            grants = grouped[email]
            enriched = [self._enrich_grant(g) for g in grants]
            keyword_set = self._collect_keywords(enriched)
            context = {
                'email': email,
                'display_name': email.split('@')[0],
                'grants': enriched,
                'keywords': sorted(keyword_set),
                'total_grants': len(enriched),
                'processing_date': self.current_date.isoformat(),
            }
            html_body = self._render_template("email_template.html", context)
            text_body = self._render_template("email_template.txt", context)

            digests.append({
                'email': email,
                'total_grants': len(enriched),
                'keywords': sorted(keyword_set),
                'html_body': html_body,
                'text_body': text_body,
                'grants': enriched,
            })
            total_grants += len(enriched)

        output_dir = ensure_directory(self.config.get_full_path('paths.output_digests_dir'))
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"email_digests_{timestamp}.json"
        else:
            output_path = Path(output_path)
            ensure_directory(output_path.parent)

        output_data = {
            'processing_date': datetime.now().isoformat(),
            'source_file': str(source_path),
            'total_recipients': len(digests),
            'total_grants': total_grants,
            'digests': digests,
        }

        save_json(output_data, output_path)
        logger.info(f"Saved {len(digests)} digests to {output_path}")
        return output_data

    def _filter_by_deadline(self, results: List[Dict[str, Any]], days_back: int = 30) -> List[Dict[str, Any]]:
        """Filter grants to include only those with deadline >= (today - days_back) or null deadline.
        
        Args:
            results: List of grant entries to filter
            days_back: Number of days back from current date to use as cutoff
            
        Returns:
            Filtered list of grants
        """
        cutoff_date = self.current_date - timedelta(days=days_back)
        filtered = []
        
        for entry in results:
            deadline_str = entry.get('deadline')
            
            # Include if deadline is null (missing)
            if not deadline_str:
                filtered.append(entry)
                continue
            
            # Parse and compare deadline
            try:
                deadline_date = date_parser.parse(deadline_str).date()
                if deadline_date >= cutoff_date:
                    filtered.append(entry)
            except Exception as e:
                logger.debug(f"Failed to parse deadline '{deadline_str}': {e} - including grant")
                filtered.append(entry)
        
        return filtered

    def _group_by_email(self, results: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for entry in results:
            base = {
                'grant_index': entry.get('grant_index'),
                'url': entry.get('url'),
                'title': entry.get('title'),
                'organization': entry.get('organization'),
                'deadline': entry.get('deadline'),
                'funding_amount': entry.get('funding_amount'),
                'abstract': entry.get('abstract'),
                'extraction_date': entry.get('extraction_date'),
            }
            for match in entry.get('matched_emails', []) or []:
                email = match.get('email')
                if not email:
                    continue
                keywords = sorted(set(match.get('matched_keywords') or []))
                grant = {**base, 'matched_keywords': keywords}
                grouped.setdefault(email, []).append(grant)
        return grouped

    def _enrich_grant(self, grant: Dict[str, Any]) -> Dict[str, Any]:
        parsed_deadline, days = self._parse_deadline(grant.get('deadline'))
        status, label = self._deadline_status(parsed_deadline, days)
        return {
            **grant,
            'parsed_deadline': parsed_deadline.isoformat() if parsed_deadline else None,
            'days_to_deadline': days,
            'deadline_status': status,
            'deadline_label': label,
        }

    def _parse_deadline(self, deadline_value: Any) -> Tuple[Optional[date], Optional[int]]:
        if not deadline_value:
            return None, None
        try:
            parsed = date_parser.parse(str(deadline_value)).date()
            days = (parsed - self.current_date).days
            return parsed, days
        except Exception:
            logger.debug(f"Could not parse deadline value: {deadline_value}")
            return None, None

    def _deadline_status(self, parsed: Optional[date], days: Optional[int]) -> Tuple[str, str]:
        if parsed is None or days is None:
            return 'missing', 'Scadenza non indicata - verificare manualmente'
        if days < 0:
            return 'past', f"Scaduto ({abs(days)} giorni fa)"
        if days < 15:
            return 'critical', f"Scadenza in {days} giorni"
        if days < 30:
            return 'warning', f"Scadenza in {days} giorni"
        return 'ok', f"Scadenza tra {days} giorni"

    def _collect_keywords(self, grants: List[Dict[str, Any]]) -> List[str]:
        keywords = set()
        for grant in grants:
            for kw in grant.get('matched_keywords') or []:
                keywords.add(kw)
        return list(keywords)

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(
                f"Template '{template_name}' not found in {self.template_dir}") from exc
        return template.render(**context)


def build_email_digests(
    source_path: Path,
    output_path: Optional[Path] = None,
    template_dir: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    """Convenience wrapper to build digests in one call."""
    builder = DigestBuilder(template_dir=template_dir, base_dir=base_dir, config=config)
    return builder.build_digests(source_path, output_path)
