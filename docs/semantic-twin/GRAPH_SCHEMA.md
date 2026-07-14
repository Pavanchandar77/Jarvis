# Semantic Twin Graph Schema v1.0.0

## Node kinds

| Kind | Required attributes | Typical edges out |
|------|---------------------|-------------------|
| application | tech_stack[], entrypoints[] | contains |
| module | path | contains, imports |
| component | framework? | renders, reads_state, calls |
| function / method / hook | signature, async? | calls, reads_state, writes_state |
| api_endpoint | method, path | calls, data_flows_to |
| state_store / state_atom | store_type | — |
| route / page | path_pattern | routes_to, renders |
| table / column | db dialect? | fk_to, contains |
| event | event_name | — |
| event_handler | — | handles, calls |
| prompt | text_ref, ordinal | — |
| requirement | text | generated_from |
| design_decision | rationale, chosen | decided_by, alternative_to |
| alternative | why_rejected | — |
| concept | slug, category | related_to |
| test | framework? | calls |
| security_surface | severity | related_to |
| perf_hotspot | complexity | related_to |

## Edge kinds & cardinality

| Kind | Source → Target | Cardinality | Cycles |
|------|-----------------|-------------|--------|
| contains | parent → child | 1:N | no |
| depends_on | A → B | N:M | no (structural) |
| imports | module → module | N:M | rare |
| calls | fn → fn | N:M | yes |
| renders | component → component | N:M | yes (rare) |
| reads_state / writes_state | code → state | N:M | no |
| routes_to | route → page | 1:N | no |
| data_flows_to | producer → consumer | N:M | yes |
| fk_to | column → column/table | N:1 | no |
| emits / handles | producer/handler ↔ event | N:M | no |
| generated_from | artifact → prompt/requirement | N:1 | no |
| decided_by | artifact → decision | N:1 | no |
| alternative_to | alternative → decision | N:1 | no |
| related_to | any → concept | N:M | yes |
| illustrates | concept → code | N:M | no |

## Difficulty score

Heuristic `0.0–1.0` from: cyclomatic proxy, fan-in/out, async boundaries,
security surfaces, framework magic.
