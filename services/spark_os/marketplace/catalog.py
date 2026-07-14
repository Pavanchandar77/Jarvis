"""Architecture Marketplace — reusable semantic architectures, not dumb templates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..architecture.designer import ArchitectureDesigner
from ..models import MarketplaceArchitecture


# Seed catalog — full semantic architectures
_SEEDS: List[Dict[str, Any]] = [
    {
        "slug": "saas",
        "name": "SaaS Multi-Tenant Platform",
        "category": "SaaS",
        "description": "Multi-tenant web SaaS with billing, auth, and admin.",
        "rationale": "Separates identity, tenancy, and product domains for scale.",
        "trade_offs": ["Complexity of tenancy isolation", "Faster enterprise sales motions"],
        "tech_stack": ["typescript", "python", "postgres"],
        "tags": ["saas", "multi-tenant", "billing"],
        "services": ["api-gateway", "auth", "billing", "app-core", "admin"],
        "apis": [
            {"name": "Login", "method": "POST", "path": "/auth/login"},
            {"name": "CreateSubscription", "method": "POST", "path": "/billing/subscriptions"},
            {"name": "ListTenants", "method": "GET", "path": "/admin/tenants"},
        ],
        "databases": ["tenants_db", "billing_db"],
        "learning": [{"title": "Multi-tenant patterns", "kind": "docs"}],
    },
    {
        "slug": "marketplace",
        "name": "Two-Sided Marketplace",
        "category": "Marketplace",
        "description": "Buyers, sellers, listings, orders, payments.",
        "rationale": "Clear bounded contexts for catalog vs fulfillment.",
        "trade_offs": ["Eventual consistency on inventory", "Higher UX complexity"],
        "tech_stack": ["typescript", "python", "postgres", "events"],
        "tags": ["marketplace", "payments"],
        "services": ["catalog", "orders", "payments", "search", "notifications"],
        "apis": [
            {"name": "SearchListings", "method": "GET", "path": "/listings"},
            {"name": "CreateOrder", "method": "POST", "path": "/orders"},
        ],
        "databases": ["catalog_db", "orders_db"],
        "learning": [{"title": "Marketplace design", "kind": "article"}],
    },
    {
        "slug": "crm",
        "name": "CRM System",
        "category": "CRM",
        "description": "Contacts, pipelines, activities, reporting.",
        "rationale": "Pipeline-centric model for sales teams.",
        "trade_offs": ["Custom fields flexibility vs query performance"],
        "tech_stack": ["python", "postgres", "react"],
        "tags": ["crm", "sales"],
        "services": ["contacts", "pipeline", "activities", "reporting"],
        "apis": [{"name": "ListContacts", "method": "GET", "path": "/contacts"}],
        "databases": ["crm_db"],
        "learning": [],
    },
    {
        "slug": "erp",
        "name": "Modular ERP",
        "category": "ERP",
        "description": "Inventory, procurement, finance modules.",
        "rationale": "Modular monolith first; extract later.",
        "trade_offs": ["Monolith simplicity vs independent deploy"],
        "tech_stack": ["python", "postgres"],
        "tags": ["erp", "modular-monolith"],
        "services": ["inventory", "procurement", "finance", "hr"],
        "apis": [{"name": "StockLevel", "method": "GET", "path": "/inventory/stock"}],
        "databases": ["erp_db"],
        "learning": [],
    },
    {
        "slug": "banking",
        "name": "Banking Core Lite",
        "category": "Banking",
        "description": "Accounts, ledgers, transfers with strict boundaries.",
        "rationale": "Ledger immutability and security boundaries first.",
        "trade_offs": ["Strict consistency vs throughput"],
        "tech_stack": ["java", "postgres"],
        "tags": ["banking", "ledger", "security"],
        "services": ["accounts", "ledger", "transfers", "fraud"],
        "apis": [{"name": "Transfer", "method": "POST", "path": "/transfers"}],
        "databases": ["ledger_db"],
        "learning": [{"title": "Double-entry basics", "kind": "docs"}],
    },
    {
        "slug": "healthcare",
        "name": "Healthcare Encounters",
        "category": "Healthcare",
        "description": "Patients, encounters, prescriptions, audit.",
        "rationale": "PHI isolation and audit trails as first-class.",
        "trade_offs": ["Compliance overhead vs speed"],
        "tech_stack": ["python", "postgres"],
        "tags": ["healthcare", "phi", "hipaa"],
        "services": ["patients", "encounters", "rx", "audit"],
        "apis": [{"name": "GetPatient", "method": "GET", "path": "/patients/{id}"}],
        "databases": ["clinical_db"],
        "learning": [],
    },
    {
        "slug": "ai-platform",
        "name": "AI Platform",
        "category": "AI Platform",
        "description": "Model gateway, evals, tool runtime, memory.",
        "rationale": "Separate inference plane from product APIs.",
        "trade_offs": ["GPU cost", "Observability complexity"],
        "tech_stack": ["python", "typescript", "redis"],
        "tags": ["ai", "llm", "agents"],
        "services": ["gateway", "orchestrator", "memory", "evals", "tools"],
        "apis": [{"name": "ChatCompletions", "method": "POST", "path": "/v1/chat/completions"}],
        "databases": ["memory_db"],
        "learning": [],
    },
    {
        "slug": "event-driven",
        "name": "Event-Driven Backbone",
        "category": "Event-driven",
        "description": "Producers, bus, consumers, sagas.",
        "rationale": "Decouple write models via async events.",
        "trade_offs": ["Debugging difficulty", "Horizontal scale"],
        "tech_stack": ["python", "events", "kafka"],
        "tags": ["events", "async"],
        "services": ["producer", "bus", "consumer-a", "consumer-b", "saga"],
        "apis": [{"name": "Publish", "method": "POST", "path": "/events"}],
        "databases": ["event_store"],
        "learning": [],
    },
    {
        "slug": "microservices",
        "name": "Microservices Starter",
        "category": "Microservices",
        "description": "Gateway + 3 services + shared auth.",
        "rationale": "Independent deploy for high-change domains.",
        "trade_offs": ["Ops cost", "Network latency"],
        "tech_stack": ["go", "postgres", "grpc"],
        "tags": ["microservices"],
        "services": ["gateway", "users", "orders", "inventory"],
        "apis": [{"name": "Health", "method": "GET", "path": "/health"}],
        "databases": ["users_db", "orders_db"],
        "learning": [],
    },
    {
        "slug": "modular-monolith",
        "name": "Modular Monolith",
        "category": "Modular Monolith",
        "description": "Single deployable with module boundaries.",
        "rationale": "Speed of monolith with module discipline.",
        "trade_offs": ["Harder isolation", "Simpler ops"],
        "tech_stack": ["python", "postgres"],
        "tags": ["modular-monolith"],
        "services": ["module-identity", "module-billing", "module-product"],
        "apis": [{"name": "AppHealth", "method": "GET", "path": "/health"}],
        "databases": ["app_db"],
        "learning": [],
    },
]


class ArchitectureMarketplace:
    def __init__(self, designer: Optional[ArchitectureDesigner] = None) -> None:
        self.designer = designer
        self._cache: List[MarketplaceArchitecture] = []
        self._build_cache()

    def _build_cache(self) -> None:
        items = []
        for seed in _SEEDS:
            arch_dict = None
            if self.designer:
                spec = self.designer.from_template(
                    seed["name"],
                    services=seed["services"],
                    apis=seed.get("apis"),
                    databases=seed.get("databases"),
                )
                arch_dict = spec.to_dict()
            items.append(
                MarketplaceArchitecture(
                    slug=seed["slug"],
                    name=seed["name"],
                    category=seed["category"],
                    description=seed["description"],
                    rationale=seed["rationale"],
                    trade_offs=list(seed.get("trade_offs") or []),
                    tech_stack=list(seed.get("tech_stack") or []),
                    architecture=arch_dict,
                    learning_resources=list(seed.get("learning") or []),
                    tags=list(seed.get("tags") or []),
                )
            )
        self._cache = items

    def list(self, category: Optional[str] = None, q: Optional[str] = None) -> List[Dict[str, Any]]:
        q_l = (q or "").lower()
        out = []
        for item in self._cache:
            if category and item.category.lower() != category.lower():
                continue
            if q_l and q_l not in (item.name + item.description + " ".join(item.tags)).lower():
                continue
            d = item.to_dict()
            # Don't dump full architecture in list
            d["architecture"] = None
            d["has_architecture"] = item.architecture is not None
            out.append(d)
        return out

    def get(self, slug: str) -> Optional[Dict[str, Any]]:
        for item in self._cache:
            if item.slug == slug:
                return item.to_dict()
        return None

    def instantiate(
        self,
        slug: str,
        *,
        name: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a live ArchitectureSpec from marketplace entry."""
        item = self.get(slug)
        if not item or not self.designer:
            return item
        seed = next(s for s in _SEEDS if s["slug"] == slug)
        spec = self.designer.from_template(
            name or seed["name"],
            services=seed["services"],
            apis=seed.get("apis"),
            databases=seed.get("databases"),
            owner=owner,
        )
        return {"marketplace": item, "architecture": spec.to_dict()}
