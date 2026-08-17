# NairaLLM Dataset Provenance & Licensing Registry

## 1. Compliance Principles & Sovereignty Rules

NairaLLM is committed to clean, transparent, and legally sovereign training data:
1. **No Closed-Model Distillation**: Zero training data sourced or generated from closed proprietary commercial LLM APIs without authorization.
2. **Permissive & Open Licensing**: All external training samples are sourced exclusively from Public Domain, MIT, Apache 2.0, BSD, CC-BY, or project-authored sources.
3. **No Unlicensed Web Scraping**: Data is not gathered via automated scraping of copyrighted articles, books, or proprietary documentation.
4. **Complete Traceability**: Every dataset entry records its provenance metadata including author, source license, domain, language, and verification checksum.

---

## 2. Provenance Metadata Schema

Every dataset sample in NairaLLM conforms to the following provenance structure:

```json
{
  "provenance_id": "prov_sem_en_001",
  "source": "nairallm_core_team",
  "license": "Apache-2.0",
  "language": "en",
  "domain": "technical_systems",
  "acquisition_method": "human_curated",
  "verified_by": "naira_runtime_audit",
  "created_at": "2026-08-15",
  "notes": "Fundamental operating system processes and scheduling explanation"
}
```

---

## 3. Registered Corpus Sources

| Dataset Component | Target Domain | Language | Permitted Licenses | Acquisition Method | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dataset A: Semantic Corpus** | General Language, Grammar | English | Public Domain / CC-BY / Project-Curated | Curated text blocks | Verified |
| **Dataset A: Semantic Corpus** | Devanagari Grammar & Syntax | Hindi | Public Domain / CC-BY / Project-Curated | Curated multilingual text | Verified |
| **Dataset A: Semantic Corpus** | Bilingual Tech Discourse | Hinglish | Project-Curated | Human curated dialogues | Verified |
| **Dataset A: Technical Corpus** | OS, Architecture, Memory | English | MIT / Apache-2.0 / Project-Authored | Open documentation | Verified |
| **Dataset A: Programming** | Python, Data Structures | Multi | MIT / Apache-2.0 | Standard algorithms | Verified |
| **Dataset B: Naira Instructions** | Intent, Tools, Plans, Safety | Multi | Project-Authored (Naira OS) | Curated scenarios | Verified |

---

## 4. Verification & Audit Checklist
- [x] All dataset files are formatted in valid JSONL.
- [x] Zero raw API keys, personal credentials, or PII.
- [x] Multilingual samples verified by native linguistic consistency.
- [x] Tool calling schemas match verified Naira OS interfaces.
