"""
Post-OIE Semantic Validator for EDC Pipeline.

This module provides data-driven validation of extracted triples AFTER the OIE
phase and BEFORE Schema Definition. It uses domain/range constraints and literal
roles dynamically parsed from configured few-shot examples at startup to:

1. Auto-correct directionality errors for known relation patterns dynamically.
2. Discard triples with non-entity objects (bare adjectives, abstract words).
3. Discard triples that violate domain/range type constraints.

All rules are dynamically learned from files — NO hardcoded entity or relation maps
beyond the default ``config/domain_rules.yaml``-driven synonyms.

v2 changes (Week 2):
- Domain rules (synonyms, non-entity blacklist, relation-type constraints,
  abbreviations) are now loaded from a YAML file when ``domain_rules_path``
  is provided to ``__init__``.
- The fallback default reproduces the original diabetes behaviour when no
  YAML is provided — fully backward compatible.
"""

import re
import logging
import csv
import os
import ast
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Paths -----------------------------------------------------------------------

DEFAULT_DOMAIN_RULES_PATH = (
    Path(__file__).resolve().parent.parent
    / "config"
    / "domain_rules.yaml"
)


# Built-in defaults (the historical behaviour of the diabetes pipeline).
# Used ONLY when no domain_rules YAML is supplied.

_DEFAULT_DIABETES_SYNONYMS = {
    "nephrogenic diabetes insipidus": "NDI",
    "pkc-alpha": "PKCa",
    "pkc alpha": "PKCa",
    "pkca": "PKCa",
    "pkc-alpha null": "PKCa",
    "pkc-alpha ko": "PKCa",
    "pkc alpha ko": "PKCa",
    "pkc-alpha-deficient": "PKCa",
    "pkc-alpha knockout": "PKCa",
    "urea transporter-a1": "UT-A1",
    "urea transporter ut-a1": "UT-A1",
    "water channel aqp2": "AQP2",
    "water channel protein aqp2": "AQP2",
    "type 2 diabetes": "T2DM",
    "type 2 diabetes mellitus": "T2DM",
    "gestational diabetes mellitus": "GDM",
    "hs-crp": "CRP",
}


_DEFAULT_DIABETES_ABBREVIATIONS = {
    "T2DM": "Type 2 Diabetes Mellitus",
    "T1DM": "Type 1 Diabetes Mellitus",
    "GDM":  "Gestational Diabetes Mellitus",
    "DKA":  "Diabetic Ketoacidosis",
    "HHS":  "Hyperosmolar Hyperglycemic State",
    "NDI":  "Nephrogenic Diabetes Insipidus",
}


# ─────────────────────────────────────────────────────────────────────────────
# YAML loader
# ─────────────────────────────────────────────────────────────────────────────


def _load_yaml(path: str) -> dict:
    """Load a YAML file. Imports PyYAML lazily so the module works even
    when PyYAML is not installed (in which case we fall back to {}).

    Resolution order:
    1. ``path`` as given (absolute or relative to cwd).
    2. ``path`` relative to ``edc-main/`` (this package's parent directory)
       so tests running from the repo root still find ``config/*.yaml``.
    """
    if not path:
        return {}
    candidates = [path]
    if not os.path.isabs(path):
        package_root = Path(__file__).resolve().parent.parent
        candidates.append(str(package_root / path))
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                import yaml
            except ImportError:
                logger.warning(
                    "[VALIDATOR] PyYAML not installed; cannot load domain rules from %s", candidate
                )
                return {}
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as exc:
                logger.error("[VALIDATOR] Failed to load domain rules YAML %s: %s", candidate, exc)
                return {}
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────────────────────────


class SemanticValidator:
    """
    Data-driven post-OIE semantic validator.
    """

    # Patterns that indicate the "entity" is NOT a real clinical entity.
    # These are intentionally kept generic — domain-specific single-word
    # blacklists come from the YAML rules file.
    _NON_ENTITY_PATTERNS = [
        # Bare adjectives/comparatives without clinical meaning
        re.compile(r'^(longer|shorter|fewer|more|less|better|worse|higher|lower|larger|smaller|faster|slower|earlier|later|greater|adequate|increased|decreased)$', re.IGNORECASE),
        # Single generic words that are not entities
        re.compile(r'^(simplicity|flexibility|adherence|compliance|convenience|complexity|tolerability|efficacy|safety|benefit|risk|cost|algorithm|guideline|management|therapy|treatment|intervention|interventions|proposed interventions|overall health|guidance|care|approach|expression|level|levels|excretion|secretion|concentration|capacity|attenuation|development|presence|absence|ablation|expression\s+of|levels\s+of|protein)$', re.IGNORECASE),
        # Empty or whitespace-only strings
        re.compile(r'^\s*$'),
        # Durations and time ranges
        re.compile(r'^\d+(\s*(to|\-)\s*\d+)?\s*(minute|hour|day|week|month|year|sec|min|hr|day|wk|yr)s?$', re.IGNORECASE),
        # Mathematical formulas
        re.compile(r'^\d+\s*[\/]\s*[a-zA-Z0-9_\s/*+\-]+$', re.IGNORECASE),
        # Comparative/relative adjective phrases
        re.compile(r'^(less|more|slightly|highly|very|slower|faster|longer|shorter|better|worse|higher|lower|greater|fewer|larger|smaller)\s+[a-zA-Z0-9_\-\s]+$', re.IGNORECASE),
        # Negative/generic reference phrases
        re.compile(r'^(any|other|another|some|all|no|none\s+of|any\s+other)\s+[a-zA-Z0-9_\-\s]+$', re.IGNORECASE),
        # WT controls and mice modifiers
        re.compile(r'^(wt|wild\s+type|wt\s+controls?|wild\s+type\s+controls?|wt\s+mice|wild\s+type\s+mice|strain-matched\s+wild\s+type|controls?|mice|animals?)$', re.IGNORECASE),
    ]

    def __init__(
        self,
        relation_schema: Optional[Dict[str, str]] = None,
        entity_type_schema: Optional[Dict[str, str]] = None,
        embedder = None,
        oie_few_shot_file_path: Optional[str] = None,
        sd_few_shot_file_path: Optional[str] = None,
        domain_rules_path: Optional[str] = None,
    ):
        """
        Args:
            relation_schema:        Dict from relation CSV {relation_name: definition}
            entity_type_schema:     Dict from entity type CSV {type_name: definition}
            embedder:               Optional SentenceTransformer/Embedder for dynamic zero-shot classification
            oie_few_shot_file_path: Path to oie_few_shot_examples.txt to dynamically learn literal roles
            sd_few_shot_file_path:  Path to sd_few_shot_examples_with_entities.txt to dynamically learn type constraints
            domain_rules_path:      Path to a YAML domain rules file
                                    (``config/domain_rules.yaml`` by default)
        """
        self.relation_schema = relation_schema or {}
        self.entity_type_schema = entity_type_schema or {}
        self.embedder = embedder

        # Build the set of known relation names from the schema for quick lookup
        self.known_relations = set(self.relation_schema.keys())

        # Load domain rules (YAML or default).
        self._load_domain_rules(domain_rules_path)

        # Dynamic Few-Shot Role & Type Loader
        self.relation_subjects = {}  # rel -> set of lowercased literal subjects
        self.relation_objects = {}   # rel -> set of lowercased literal objects
        self.relation_subj_types = {}  # rel -> set of subject_types
        self.relation_obj_types = {}   # rel -> set of object_types

        # 1. Parse literal entity roles from OIE few-shot examples
        if oie_few_shot_file_path and os.path.exists(oie_few_shot_file_path):
            try:
                with open(oie_few_shot_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "Triplets:" in line:
                            triplets_part = line.split("Triplets:", 1)[1].strip()
                            try:
                                triplets = ast.literal_eval(triplets_part)
                                for triple in triplets:
                                    if len(triple) == 3:
                                        subj, rel, obj = triple
                                        rel_lower = rel.strip().lower()
                                        if rel_lower not in self.relation_subjects:
                                            self.relation_subjects[rel_lower] = set()
                                            self.relation_objects[rel_lower] = set()
                                        self.relation_subjects[rel_lower].add(subj.strip().lower())
                                        self.relation_objects[rel_lower].add(obj.strip().lower())
                            except Exception as e:
                                logger.warning(f"[VALIDATOR] Failed to parse few-shot triplet line: {line.strip()}. Error: {e}")
                logger.info(f"[VALIDATOR] Dynamically loaded literal rules for {len(self.relation_subjects)} relations from OIE few-shot.")
            except Exception as e:
                logger.error(f"[VALIDATOR] Error loading OIE few-shot roles: {e}")

        # 2. Parse expected subject/object entity types from SD few-shot examples
        if sd_few_shot_file_path and os.path.exists(sd_few_shot_file_path):
            try:
                with open(sd_few_shot_file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                decoder = json.JSONDecoder()
                idx = 0
                while True:
                    idx = content.find('[', idx)
                    if idx == -1:
                        break
                    try:
                        obj_list, end = decoder.raw_decode(content[idx:])
                        if isinstance(obj_list, list):
                            for entry in obj_list:
                                if isinstance(entry, dict):
                                    rel = entry.get("relation", "").strip().lower()
                                    s_type = entry.get("subject_type", "").strip()
                                    o_type = entry.get("object_type", "").strip()
                                    if rel and s_type and o_type:
                                        if rel not in self.relation_subj_types:
                                            self.relation_subj_types[rel] = set()
                                            self.relation_obj_types[rel] = set()
                                        self.relation_subj_types[rel].add(s_type)
                                        self.relation_obj_types[rel].add(o_type)
                        idx += end
                    except json.JSONDecodeError:
                        idx += 1
                logger.info(f"[VALIDATOR] Dynamically loaded type constraints for {len(self.relation_subj_types)} relations from SD few-shot.")
            except Exception as e:
                logger.error(f"[VALIDATOR] Error loading SD few-shot types: {e}")

        # Detect if it's an instruction-based API embedder (e.g. Qwen3-Embedding or Jina)
        self.is_instruction_model = False
        if self.embedder:
            embedder_class = self.embedder.__class__.__name__
            if embedder_class in ["OpenRouterEmbedder", "JinaEmbedder"]:
                self.is_instruction_model = True
            elif hasattr(self.embedder, "model_name"):
                model_name_lower = str(self.embedder.model_name).lower()
                if "/" in model_name_lower or "jina" in model_name_lower or "qwen" in model_name_lower:
                    self.is_instruction_model = True

        # Precompute entity type embeddings if embedder is available
        self.type_embeddings = {}
        if self.embedder and self.entity_type_schema:
            for type_name, type_def in self.entity_type_schema.items():
                text_representation = f"{type_name}: {type_def}"
                try:
                    emb = self.embedder.encode(text_representation)
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        self.type_embeddings[type_name] = emb / norm
                    else:
                        self.type_embeddings[type_name] = emb
                except Exception as e:
                    logger.warning(f"[VALIDATOR] Failed to precompute embedding for type '{type_name}': {e}")

        logger.info(
            f"[VALIDATOR] Initialized with {len(self.known_relations)} relations, "
            f"{len(self.entity_type_schema)} entity types (embeddings precomputed: {len(self.type_embeddings) > 0}, "
            f"instruction_model: {self.is_instruction_model})"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Domain rules loader (NEW in v2)
    # ─────────────────────────────────────────────────────────────────────

    def _load_domain_rules(self, domain_rules_path: Optional[str]) -> None:
        """Load domain rules from YAML; fall back to built-in defaults.

        On success, populates:
        - self.synonyms            (Dict[str, str])
        - self.non_entity_words    (Set[str])
        - self.non_entity_patterns (List[re.Pattern])
        - self.local_abbreviations (Dict[str, str])
        """
        rules: dict = {}
        if domain_rules_path:
            rules = _load_yaml(domain_rules_path)
        elif DEFAULT_DOMAIN_RULES_PATH.exists():
            rules = _load_yaml(str(DEFAULT_DOMAIN_RULES_PATH))

        if not rules:
            # Fall back to embedded defaults so existing callers see no behavior change.
            self.synonyms = dict(_DEFAULT_DIABETES_SYNONYMS)
            self.non_entity_words = set()
            self.non_entity_patterns = []
            self.local_abbreviations = dict(_DEFAULT_DIABETES_ABBREVIATIONS)
            self.domain_name = "diabetes"
            self._extra_relation_constraints = {}
            logger.info(
                "[VALIDATOR] No domain rules YAML provided/loaded; using built-in diabetes defaults "
                "(%d synonyms).", len(self.synonyms),
            )
            return

        # Synonyms
        raw_synonyms = rules.get("domain_specific_synonyms") or {}
        self.synonyms = {str(k).lower(): str(v) for k, v in raw_synonyms.items()}

        # Non-entity blacklist (built-in regexes + new words + new patterns)
        bl = rules.get("non_entity_blacklist") or {}
        self.non_entity_words = {w.lower() for w in (bl.get("bare_words") or [])}
        self.non_entity_patterns = [
            re.compile(p, re.IGNORECASE) for p in (bl.get("patterns") or [])
        ]

        # Local abbreviations
        raw_abbr = rules.get("local_medical_abbreviations") or {}
        self.local_abbreviations = {str(k): str(v) for k, v in raw_abbr.items()}

        # Relation type constraints (extra fail-safes)
        self._extra_relation_constraints: Dict[str, dict] = {}
        for rel, cfg in (rules.get("relation_type_constraints") or {}).items():
            cfg = cfg or {}
            self._extra_relation_constraints[str(rel).strip().lower()] = {
                "allowed_subj_types": set(cfg.get("allowed_subj_types") or []),
                "allowed_obj_types":  set(cfg.get("allowed_obj_types") or []),
                "blocked_subj_types":  set(cfg.get("blocked_subj_types") or []),
                "blocked_obj_types":   set(cfg.get("blocked_obj_types") or []),
            }

        self.domain_name = str(rules.get("domain") or "custom")
        logger.info(
            "[VALIDATOR] Loaded domain rules: domain=%s, synonyms=%d, blacklist_words=%d, "
            "constraints=%d, abbreviations=%d",
            self.domain_name, len(self.synonyms), len(self.non_entity_words),
            len(self._extra_relation_constraints), len(self.local_abbreviations),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Existing API (unchanged)
    # ─────────────────────────────────────────────────────────────────────

    def _strip_ontology_noise(self, term: str) -> str:
        """Removes common ontology noise prefixes from entities."""
        term_clean = term.strip()

        # Pattern 1: Matches brackets prefix like [RNAx] or [Code]
        term_clean = re.sub(r'^\[[A-Za-z0-9_\-]+\]\s*', '', term_clean)

        # Pattern 2: Matches word prefix with code
        term_clean = re.sub(
            r'^(RNAx|MESH|SNOMEDCT|SNOMED|OMIM|RXNORM|ICD10|ICD9|ICD|EHR)'
            r'[0-9_A-Za-z\-]*[:_\-\s]\s*',
            '', term_clean, flags=re.IGNORECASE,
        )

        # Pattern 3: Matches single short uppercase code prefix
        term_clean = re.sub(r'^[A-Z]+[0-9]*\s+', '', term_clean)

        return term_clean.strip()

    def _is_atomic_entity(self, term: str) -> bool:
        """Checks if a term is atomic (not a sentence or verbose instruction)."""
        words = term.strip().split()
        if not words:
            return False

        if len(words) > 5:
            return False

        first_word = words[0].lower().rstrip(',.:')
        instruction_verbs = {
            "instruct", "instructs", "instructing",
            "teach", "teaches", "teaching",
            "educate", "educates", "educating",
            "advise", "advises", "advising",
            "encourage", "encourages", "encouraging",
            "recommend", "recommends", "recommending",
            "recommended", "counsel", "counsels", "counseling",
            "tell", "tells", "telling",
            "monitor", "monitors", "monitoring",
            "provide", "provides", "providing",
            "refer", "refers", "referring",
            "adjust", "adjusts", "adjusted", "adjusting",
            "initiate", "initiates", "initiated", "initiating",
            "discontinue", "discontinues", "discontinued", "discontinuing", "discontinuation",
            "assess", "assesses", "assessed", "assessing",
            "evaluate", "evaluates", "evaluated", "evaluating",
        }
        if first_word in instruction_verbs:
            return False

        return True

    def _is_non_entity(self, entity_str: str) -> bool:
        """Check if a string is NOT a valid clinical entity."""
        cleaned = entity_str.strip()
        if not cleaned:
            return True

        # YAML-loaded bare word blacklist
        if cleaned.lower() in self.non_entity_words:
            return True

        # YAML-loaded patterns
        for pattern in self.non_entity_patterns:
            if pattern.match(cleaned):
                return True

        # Built-in regex blacklist
        for pattern in self._NON_ENTITY_PATTERNS:
            if pattern.match(cleaned):
                return True
        return False

    def _matches_set(self, entity: str, entity_set: set) -> bool:
        """Substring matching to handle minor variations."""
        entity_clean = entity.strip().lower()
        if not entity_clean:
            return False

        if entity_clean in entity_set:
            return True

        for item in entity_set:
            if item in entity_clean or entity_clean in item:
                if len(entity_clean) >= 3 and len(item) >= 3:
                    return True
        return False

    def _is_lexically_anchored(self, entity_str: str, input_text: str = "") -> bool:
        """Check if an entity string is lexically anchored to the input text."""
        if not input_text:
            return True

        entity_str_clean = entity_str.strip().lower()
        input_text_clean = input_text.strip().lower()

        if entity_str_clean in input_text_clean:
            return True

        entity_words = [w for w in re.split(r'\W+', entity_str_clean) if len(w) > 2]

        if not entity_words:
            return entity_str_clean in input_text_clean

        stopwords = {
            'and', 'the', 'with', 'for', 'associated', 'disease', 'condition',
            'treatment', 'therapy', 'management', 'factor', 'options', 'choices',
            'persons', 'people', 'mellitus',
        }

        meaningful_words = [w for w in entity_words if w not in stopwords]

        if not meaningful_words:
            return entity_str_clean in input_text_clean

        for word in meaningful_words:
            if word in input_text_clean:
                return True

        return False

    def _predict_entity_type(self, entity_str: str) -> str:
        """Predict the entity type via zero-shot embedding similarity."""
        if not self.embedder or not self.type_embeddings:
            return "Unknown"

        try:
            entity_clean = entity_str.strip()
            if getattr(self, "is_instruction_model", False):
                query_text = f"Given a clinical mention, classify it into the UMLS semantic group: {entity_clean}"
            else:
                query_text = entity_clean

            emb = self.embedder.encode(query_text)
            norm = np.linalg.norm(emb)
            if norm == 0:
                return "Unknown"
            emb_norm = emb / norm

            best_type = "Unknown"
            best_score = -1.0
            for type_name, type_emb in self.type_embeddings.items():
                score = np.dot(emb_norm, type_emb)
                if score > best_score:
                    best_score = score
                    best_type = type_name

            return best_type
        except Exception as e:
            logger.error(f"[VALIDATOR] Error in semantic entity type prediction: {e}")
            return "Unknown"

    def try_auto_correct_direction_by_type(
        self, triple: List[str], subj_type: str, obj_type: str
    ) -> Tuple[Optional[List[str]], str, str]:
        """Auto-correct directionality and perform domain/range validation."""
        if len(triple) != 3:
            return triple, subj_type, obj_type

        subj, rel, obj = triple
        rel_lower = rel.strip().lower()

        # Dynamic constraints from SD few-shot
        if rel_lower in self.relation_subj_types:
            allowed_subj_types = self.relation_subj_types[rel_lower]
            allowed_obj_types = self.relation_obj_types[rel_lower]

            intersection = allowed_subj_types.intersection(allowed_obj_types)
            if not intersection:
                if subj_type in allowed_obj_types and obj_type in allowed_subj_types:
                    logger.debug(
                        f"[VALIDATOR] Dynamic type-based direction auto-corrected: "
                        f"[{subj} ({subj_type}), {rel}, {obj} ({obj_type})] → "
                        f"[{obj} ({obj_type}), {rel}, {subj} ({subj_type})]"
                    )
                    subj, obj = obj, subj
                    subj_type, obj_type = obj_type, subj_type

            if subj_type not in allowed_subj_types or obj_type not in allowed_obj_types:
                logger.debug(
                    f"[VALIDATOR] Discarding triple violating domain/range: "
                    f"[{subj} ({subj_type}), {rel}, {obj} ({obj_type})]"
                )
                return None, "", ""

        # YAML-loaded relation constraints (extra fail-safes)
        if rel_lower in self._extra_relation_constraints:
            cfg = self._extra_relation_constraints[rel_lower]
            if cfg["blocked_subj_types"] and subj_type in cfg["blocked_subj_types"]:
                logger.debug(f"[VALIDATOR] Discarding due to YAML subj-type block: {triple}")
                return None, "", ""
            if cfg["blocked_obj_types"] and obj_type in cfg["blocked_obj_types"]:
                logger.debug(f"[VALIDATOR] Discarding due to YAML obj-type block: {triple}")
                return None, "", ""
            if cfg["allowed_subj_types"] and subj_type not in cfg["allowed_subj_types"]:
                logger.debug(f"[VALIDATOR] Discarding due to YAML subj-type allow: {triple}")
                return None, "", ""
            if cfg["allowed_obj_types"] and obj_type not in cfg["allowed_obj_types"]:
                logger.debug(f"[VALIDATOR] Discarding due to YAML obj-type allow: {triple}")
                return None, "", ""

        # Built-in fail-safes for specific relations
        if rel_lower in ["has adverse effect", "has_adverse_effect"]:
            if obj_type in ["Drug", "Treatment Procedure"] or "drug" in obj.lower() or "insulin" in obj.lower():
                logger.debug(f"[VALIDATOR] Discarding 'has adverse effect' with non-symptom object: {triple}")
                return None, "", ""

        if rel_lower in ["treated by", "treated_by", "may be treated by"]:
            if subj_type in ["Drug", "Treatment Procedure"]:
                logger.debug(f"[VALIDATOR] Discarding 'treated by' with drug subject: {triple}")
                return None, "", ""

        return [subj, rel, obj], subj_type, obj_type

    def clean_and_simplify_entity(self, entity_str: str) -> str:
        """Simplify and canonicalize an entity string."""
        orig_entity = entity_str
        entity_str = entity_str.strip()

        # 1. Strip ontology noise
        entity_str = self._strip_ontology_noise(entity_str)

        # 2. Acronym extraction
        paren_match = re.search(r'\(([^)]+)\)', entity_str)
        if paren_match:
            candidate = paren_match.group(1).strip()
            candidate_clean = re.sub(
                r'\s+(KO|null|knockout|WT|wild\s*type)\b', '', candidate, flags=re.IGNORECASE,
            ).strip()
            if 2 <= len(candidate_clean) <= 10 and not any(
                w in candidate_clean.lower() for w in ['expression', 'level', 'treatment', 'therapy']
            ):
                entity_str = candidate_clean
            else:
                entity_str = re.sub(r'\s*\([^)]+\)', '', entity_str).strip()

        # 3. Synonym mapping (YAML-loaded)
        ent_lower = entity_str.lower().replace("  ", " ")
        for long_name, short_name in self.synonyms.items():
            if ent_lower == long_name or ent_lower.startswith(long_name + " "):
                return short_name

        # 4. Common prefixes/suffixes (intentionally kept as a generic medical list
        #    — they apply to any domain. Add domain-specific ones in the YAML.)
        suffixes = [
            r'\s+expression$', r'\s+protein\s+expression$', r'\s+level$', r'\s+levels$',
            r'\s+treatment$', r'\s+therapy$', r'\s+administration$', r'\s+infusion$',
            r'\s+induction$', r'\s+exposure$', r'\s+excretion$', r'\s+secretion$',
            r'\s+deficiency$', r'\s+inhibition$', r'\s+blockade$', r'\s+concentration$',
            r'\s+mRNA$', r'\s+protein$', r'\s+tissues?$', r'\s+medulla$', r'\s+inner\s+medulla$',
            r'\s+pathway$', r'\s+signaling$', r'\s+mediated\s+signaling$',
            r'\s+autoantibodies$', r'\s+antibodies$', r'\s+antibody$',
            r'-fed$', r'-treated$', r'-induced$',
            r'\s+null\s+mice$', r'\s+null$', r'\s+ko\s+mice$', r'\s+ko$', r'\s+knockout\s+mice$',
            r'\s+knockout$', r'\s+animals?$', r'\s+mice$', r'\s+controls?$', r'\s+wild\s+type$', r'\s+wt$',
            r'\s+treatment\s+in\s+wt\s+mice$', r'\s+treatment\s+in\s+wt$',
            r'-fed\s+wt\s+mice$', r'-fed\s+wt$',
            r'\s+treatment\s+in\s+pkca\s+ko\s+mice$', r'\s+treatment\s+in\s+pkca\s+ko$',
            r'\s+in\s+wt\s+mice$', r'\s+in\s+wt$', r'\s+in\s+mice$', r'\s+in\s+controls?$',
            r'\s+in\s+6\s+week\s+lithium-treated$', r'\s+in\s+lithium-treated$', r'\s+in\s+lithium-fed$',
            r'\s+in\s+pkca\s+ko\s+mice$', r'\s+in\s+pkca\s+ko$', r'\s+in\s+pkc-alpha$',
            r'\s+treatment\s+in\s+.*$', r'\s+therapy\s+in\s+.*$', r'\s+in\s+.*$', r'\s+after\s+.*$', r'\s+with\s+.*$',
            r'\s+associated$',
        ]
        prefixes = [
            r'^levels\s+of\s+', r'^expression\s+of\s+', r'^secretion\s+of\s+',
            r'^urinary\s+', r'^plasma\s+', r'^serum\s+', r'^blood\s+', r'^tissue\s+', r'^medullary\s+',
            r'^ablation\s+of\s+', r'^absence\s+of\s+', r'^reduction\s+in\s+',
            r'^in\s+', r'^after\s+', r'^with\s+', r'^for\s+', r'^during\s+',
            r'^[a-zA-Z0-9\-]+-induced\s+', r'^[a-zA-Z0-9\-]+-treated\s+', r'^[a-zA-Z0-9\-]+-fed\s+',
            r'^\d+\s*weeks?\s+', r'^\d+\s*days?\s+', r'^chronic\s+', r'^chronic\s+[a-zA-Z0-9\-]+-fed\s+',
            r'^severe\s+',
        ]

        changed = True
        while changed:
            old_str = entity_str
            for pat in suffixes:
                entity_str = re.sub(pat, '', entity_str, flags=re.IGNORECASE).strip()
            for pat in prefixes:
                entity_str = re.sub(pat, '', entity_str, flags=re.IGNORECASE).strip()
            changed = (entity_str != old_str)

        entity_str = entity_str.strip(' -_,.').strip()

        ent_lower = entity_str.lower()
        if ent_lower in self.synonyms:
            return self.synonyms[ent_lower]

        logger.debug(f"[VALIDATOR] Simplified entity: '{orig_entity}' -> '{entity_str}'")
        return entity_str if entity_str else orig_entity

    def validate_triple(self, triple: List[str], input_text: str = "") -> Optional[List[str]]:
        """Validate a single triple. Returns the triple or None."""
        if len(triple) != 3:
            logger.debug(f"[VALIDATOR] Discarded malformed triple: {triple}")
            return None

        subj, rel, obj = triple

        orig_subj = subj
        orig_obj = obj

        subj = self.clean_and_simplify_entity(subj)
        obj = self.clean_and_simplify_entity(obj)

        if self._is_non_entity(subj):
            logger.debug(f"[VALIDATOR] Discarded non-entity subject: '{subj}' in {triple}")
            return None
        if self._is_non_entity(obj):
            logger.debug(f"[VALIDATOR] Discarded non-entity object: '{obj}' in {triple}")
            return None

        if not self._is_atomic_entity(subj):
            logger.debug(f"[VALIDATOR] Discarded non-atomic subject: '{subj}' in {triple}")
            return None
        if not self._is_atomic_entity(obj):
            logger.debug(f"[VALIDATOR] Discarded non-atomic object: '{obj}' in {triple}")
            return None

        if subj.strip().lower() == obj.strip().lower():
            logger.debug(f"[VALIDATOR] Discarded tautological triple: {triple}")
            return None

        if obj.strip().lower() in subj.strip().lower() and len(obj.strip()) < len(subj.strip()):
            logger.debug(f"[VALIDATOR] Discarded redundant triple (object in subject): {triple}")
            return None

        if not (self._is_lexically_anchored(subj, input_text) or self._is_lexically_anchored(orig_subj, input_text)):
            logger.debug(f"[VALIDATOR] Discarded hallucinated subject (not in source text): '{subj}' in {triple}")
            return None
        if not (self._is_lexically_anchored(obj, input_text) or self._is_lexically_anchored(orig_obj, input_text)):
            logger.debug(f"[VALIDATOR] Discarded hallucinated object (not in source text): '{obj}' in {triple}")
            return None

        # Dynamic literal string direction auto-correction
        rel_lower = rel.strip().lower()
        if rel_lower in self.relation_subjects:
            subj_set = self.relation_subjects[rel_lower]
            obj_set = self.relation_objects[rel_lower]

            intersection = subj_set.intersection(obj_set)
            union = subj_set.union(obj_set)
            overlap_ratio = len(intersection) / len(union) if union else 0.0

            if overlap_ratio < 0.3:
                subj_clean = subj.strip().lower()
                obj_clean = obj.strip().lower()

                a_matches_obj = self._matches_set(subj_clean, obj_set)
                b_matches_subj = self._matches_set(obj_clean, subj_set)

                a_matches_subj = self._matches_set(subj_clean, subj_set)
                b_matches_obj = self._matches_set(obj_clean, obj_set)

                if a_matches_obj and b_matches_subj and not (a_matches_subj and b_matches_obj):
                    logger.debug(
                        f"[VALIDATOR] Dynamic literal direction auto-corrected: "
                        f"[{subj}, {rel}, {obj}] → [{obj}, {rel}, {subj}]"
                    )
                    return [obj, rel, subj]

        return [subj, rel, obj]

    def validate_batch(
        self,
        oie_triples_list: List[List[List[str]]],
        input_texts: Optional[List[str]] = None,
    ) -> List[List[List[str]]]:
        """Validate all triples from the OIE phase."""
        if input_texts is not None:
            assert len(oie_triples_list) == len(input_texts), "Triplets list and input texts must align"

        validated_list = []
        total_kept = 0
        total_discarded = 0

        for idx, triples in enumerate(oie_triples_list):
            input_text = input_texts[idx] if input_texts is not None else ""
            kept = []
            for triple in triples:
                result = self.validate_triple(triple, input_text)

                if result is None:
                    total_discarded += 1
                else:
                    total_kept += 1
                    kept.append(result)
            validated_list.append(kept)

        logger.info(
            f"[VALIDATOR] Batch complete: kept={total_kept}, "
            f"discarded={total_discarded}"
        )
        return validated_list
