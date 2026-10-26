"""The LeaseLens contract-review workflow.

A plain, explicit orchestration of these stages (no agent framework needed):

    1. input check       - the extracted text the user reviewed
    2. segmentation      - split into clauses with page numbers
    3. safety check      - flag prompt-injection attempts
    4. rule screening    - deterministic keyword rules
    5. AI analysis       - Gemma classifies clauses in small batches (JSON, validated)
    6. retrieval         - TF-IDF search of the local guidance for each finding
    7. risk assessment   - combine rules + AI transparently
    8. ready for review  - nothing is sent, signed or changed

Email drafting is a separate step the user starts after reviewing findings.
"""

from __future__ import annotations

import logging

from app.agents.audit import AuditTrail
from app.core.config import Settings
from app.core.errors import ExtractionError, LimitExceededError
from app.providers.base import AIProvider
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, Finding, KnowledgeReference, RuleHit
from app.schemas.common import DISCLAIMER
from app.services.clause_analysis import AIFinding, analyze_batch
from app.services.clause_segmentation import Clause, split_into_clauses
from app.services.injection import looks_like_injection
from app.services.knowledge_base import KnowledgeBase
from app.services.retrieval import TfidfRetriever
from app.services.risk_scoring import DISPLAY_ORDER, combine, highest_rule_level, summarize
from app.services.rule_screening import screen_clauses

logger = logging.getLogger("leaselens.workflow")

EXCERPT_CHARS = 900


class ContractReviewWorkflow:
    def __init__(self, settings: Settings, kb: KnowledgeBase, retriever: TfidfRetriever) -> None:
        self.settings = settings
        self.kb = kb
        self.retriever = retriever

    async def run(self, request: AnalyzeRequest, provider: AIProvider) -> AnalyzeResponse:
        audit = AuditTrail()
        warnings: list[str] = []

        # 1. Input check ------------------------------------------------------
        total_chars = sum(len(p.text) for p in request.pages)
        if total_chars > self.settings.max_text_chars:
            raise LimitExceededError(
                f"The text is longer than the {self.settings.max_text_chars:,} character limit."
            )
        if sum(len(p.text.strip()) for p in request.pages) < 20:
            raise ExtractionError("There is no text to analyse. Extract a document first.")
        audit.add("input", "completed", f"Received {len(request.pages)} page(s) with {total_chars:,} characters.")

        # 2. Segmentation -----------------------------------------------------
        clauses = split_into_clauses(request.pages)
        by_id = {c.id: c for c in clauses}
        audit.add("segmentation", "completed", f"Split the text into {len(clauses)} clause(s).")

        # 3. Prompt-injection check ------------------------------------------
        suspicious = {c.id for c in clauses if looks_like_injection(c.text)}
        if suspicious:
            pages = sorted({by_id[cid].page for cid in suspicious})
            message = (
                "Some text looks like instructions aimed at an AI system (possible prompt injection) on page(s) "
                f"{', '.join(map(str, pages))}. It was treated as contract text only, and the keyword rules "
                "were applied independently of the AI."
            )
            warnings.append(message)
            audit.add("safety_check", "warning", message, [f"page {p}" for p in pages])
        else:
            audit.add("safety_check", "completed", "No instruction-like text found in the document.")

        # 4. Rule screening ---------------------------------------------------
        rule_hits = screen_clauses(clauses, self.kb)
        rule_ids = sorted({hit.rule_id for cats in rule_hits.values() for hits in cats.values() for hit in hits})
        audit.add(
            "rule_screening",
            "completed",
            f"{len(rule_hits)} clause(s) matched {len(rule_ids)} keyword rule(s).",
            rule_ids,
        )

        # 5. AI analysis ------------------------------------------------------
        selected = self._select_for_ai(clauses, rule_hits)
        if len(selected) < len(clauses):
            warnings.append(
                f"The document has {len(clauses)} clauses; the AI reviewed {len(selected)} of them "
                "(clauses matching keyword rules first). Keyword rules were applied to all clauses."
            )
        ai_findings, failed_batches, batch_count = await self._run_ai(
            selected, request.category, provider, audit
        )
        if batch_count and failed_batches == batch_count:
            ai_status = "failed"
            warnings.append(
                "The AI did not return usable results, so the findings below come from the keyword rules only. "
                "You can retry the analysis."
            )
        elif failed_batches:
            ai_status = "partial"
            warnings.append(
                f"The AI could not analyse {failed_batches} of {batch_count} group(s) of clauses. "
                "Keyword-rule findings are still shown for those clauses."
            )
        else:
            ai_status = "completed"

        # 6 + 7. Retrieval and risk assessment -------------------------------
        findings = self._build_findings(by_id, rule_hits, ai_findings, suspicious, request.category)
        sources = sorted({ref.source_id for f in findings for ref in f.references})
        without_refs = sum(1 for f in findings if not f.references)
        audit.add(
            "retrieval",
            "completed" if not without_refs else "warning",
            f"Matched local guidance for {len(findings) - without_refs} of {len(findings)} finding(s)."
            + (f" {without_refs} finding(s) had no matching guidance." if without_refs else ""),
            sources,
        )
        summary = summarize(findings)
        audit.add("risk_assessment", "completed", summary.headline)

        # 8. Hand over to the user -------------------------------------------
        audit.add(
            "review",
            "completed",
            "Findings are ready for your review. Nothing was sent, signed or changed.",
        )
        logger.info(
            "analysis done provider=%s clauses=%d findings=%d ai_status=%s",
            provider.name, len(clauses), len(findings), ai_status,
        )
        return AnalyzeResponse(
            provider=provider.name,
            model=provider.model,
            processed_locally=provider.is_local,
            category=request.category,
            ai_status=ai_status,
            summary=summary,
            findings=findings,
            warnings=warnings,
            audit=audit.events,
            disclaimer=DISCLAIMER,
        )

    def _select_for_ai(self, clauses: list[Clause], rule_hits: dict[str, dict[str, list[RuleHit]]]) -> list[Clause]:
        limit = self.settings.max_clauses_for_ai
        if len(clauses) <= limit:
            return clauses
        flagged = [c for c in clauses if c.id in rule_hits]
        others = [c for c in clauses if c.id not in rule_hits]
        chosen = {c.id for c in (flagged + others)[:limit]}
        return [c for c in clauses if c.id in chosen]  # keep document order

    async def _run_ai(
        self, clauses: list[Clause], category: str, provider: AIProvider, audit: AuditTrail
    ) -> tuple[dict[tuple[str, str], AIFinding], int, int]:
        size = self.settings.ai_batch_size
        batches = [clauses[i : i + size] for i in range(0, len(clauses), size)]
        results: dict[tuple[str, str], AIFinding] = {}
        failed = 0
        for number, batch in enumerate(batches, start=1):
            label = f"Batch {number}/{len(batches)} (pages {batch[0].page}-{batch[-1].page})"
            outcome = await analyze_batch(provider, batch, category, self.kb)
            if outcome.retried:
                audit.add("ai_analysis", "retried", f"{label}: the model's answer was not valid JSON; asked again.")
            if outcome.failed:
                failed += 1
                audit.add("ai_analysis", "failed", f"{label}: no valid answer after a retry; using keyword rules only.")
                continue
            for finding in outcome.findings:
                results[(finding.clause_id, finding.category)] = finding
            detail = f"{label}: {provider.label} ({provider.model}) returned {len(outcome.findings)} finding(s)."
            if outcome.dropped:
                detail += f" Ignored {outcome.dropped} item(s) with unknown clause ids or categories."
            audit.add("ai_analysis", "completed" if not outcome.dropped else "warning", detail)
        return results, failed, len(batches)

    def _build_findings(
        self,
        clauses: dict[str, Clause],
        rule_hits: dict[str, dict[str, list[RuleHit]]],
        ai_findings: dict[tuple[str, str], AIFinding],
        suspicious: set[str],
        document_category: str,
    ) -> list[Finding]:
        keys = {(cid, cat) for cid, cats in rule_hits.items() for cat in cats} | set(ai_findings)
        findings: list[Finding] = []
        for clause_id, category in keys:
            clause = clauses[clause_id]
            hits = rule_hits.get(clause_id, {}).get(category, [])
            ai = ai_findings.get((clause_id, category))
            rule_level = highest_rule_level([h.level for h in hits])
            assessment = combine(rule_level, ai.risk_level if ai else None, ai.confidence if ai else None)

            references = self.retriever.search(clause.text, category, document_category)
            notes = list(assessment.notes)
            if not references:
                notes.append("No local guidance entry matched this clause.")
            if clause_id in suspicious:
                notes.append("This clause contains text that looks like instructions to an AI; it was treated as contract text.")

            questions = ai.questions if ai and ai.questions else self._guidance_questions(references)
            excerpt = clause.text if len(clause.text) <= EXCERPT_CHARS else clause.text[:EXCERPT_CHARS].rstrip() + "…"
            findings.append(
                Finding(
                    id=f"{clause_id}:{category}",
                    clause_id=clause_id,
                    category=category,
                    category_label=self.kb.label_for(category),
                    excerpt=excerpt,
                    page=clause.page,
                    risk_level=assessment.level,
                    reason=(ai.reason if ai and ai.reason else " ".join(h.description for h in hits))
                    or "Flagged for review.",
                    impact=ai.impact if ai and ai.impact else "Not assessed by the AI. Read the clause and the guidance below.",
                    questions=questions,
                    references=references,
                    rule_hits=hits,
                    rule_level=rule_level,
                    ai_level=ai.risk_level if ai else None,
                    assessed_by=(["rules"] if hits else []) + (["ai"] if ai else []),
                    evidence_agreement=assessment.agreement,
                    uncertainty_notes=notes,
                )
            )
        findings.sort(key=lambda f: (DISPLAY_ORDER[f.risk_level], f.page or 0, f.clause_id))
        return findings

    def _guidance_questions(self, references: list[KnowledgeReference]) -> list[str]:
        for ref in references:
            entry = self.kb.entry(ref.source_id)
            if entry:
                return entry.questions[:3]
        return []
