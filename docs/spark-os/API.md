# Spark OS API Surface (`/api/os`)

| Method | Path | Capability |
|--------|------|------------|
| GET | `/status` | Health + capability list |
| POST | `/architecture` | Design architecture (or template) |
| GET | `/architecture` | List architectures |
| GET | `/architecture/{id}` | Get architecture |
| POST | `/architecture/compile` | Compile → code + twin + review |
| GET/POST | `/requirements/{twin_id}` | Living requirements |
| GET | `/requirements/{twin_id}/trace/{id}` | Full requirement trace |
| POST | `/review/{twin_id}` | Autonomous design review |
| POST | `/agents/{twin_id}/bootstrap` | Multi-agent ownership |
| GET | `/agents/{project_id}/status` | Agent bus status |
| POST | `/agents/{project_id}/message` | Claim/delegate/negotiate |
| POST | `/agents/{project_id}/approve/{id}` | Architect approval |
| GET | `/timeline/{twin_id}` | Time machine history |
| GET | `/timeline/{twin_id}/scrub/{rev}` | Scrub narrative |
| POST | `/simulate/{twin_id}` | Pure simulation |
| GET | `/memory/search` | Org memory retrieve |
| POST | `/memory/learn/{twin_id}` | Learn from twin |
| GET | `/runtime/{twin_id}/visualization` | Live path frames |
| GET | `/marketplace` | List architectures |
| GET | `/marketplace/{slug}` | Blueprint detail |
| POST | `/marketplace/{slug}/use` | Instantiate design |
| GET | `/refactor/catalog` | Transformations |
| POST | `/refactor/{twin_id}` | Propose or full pipeline |

UI: `/spark-os?twin=<twin_id>`
