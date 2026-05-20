

# Keyword-based intent classification
# Day 13 replaces with GPT-4o structured output

from enum import Enum
from typing import List, Dict

class QueryIntent(str, Enum):
    WRITE_TICKET     = "write_ticket"
    WRITE_METADATA   = "write_metadata"
    WRITE_RULE       = "write_rule"
    FULL_DIAGNOSTIC  = "full_diagnostic"
    DATA_QUALITY     = "data_quality"
    GOVERNANCE       = "governance"
    INCIDENT_REVIEW  = "incident_review"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    METRIC_ANALYSIS  = "metric_analysis"
    UNKNOWN          = "unknown"


INTENT_RULES: Dict[QueryIntent, List[str]] = {
    QueryIntent.WRITE_TICKET:    [
        "create ticket",
        "create a bug",
        "open bug",
        "raise issue","log incident","file a ticket",
    ],
    QueryIntent.WRITE_METADATA:  [
        "update owner","set owner","update metadata",
        "classify","update description",
    ],
    QueryIntent.WRITE_RULE:      [
        "create rule","add rule","define rule",
        "new rule","create dq rule",
    ],
    QueryIntent.FULL_DIAGNOSTIC: [
        "why did","root cause","investigate",
        "explain why","diagnose","what happened",
    ],
    QueryIntent.DATA_QUALITY:    [
        "data quality","dq score","completeness",
        "accuracy","quality score",
    ],
    QueryIntent.GOVERNANCE:      [
        "who owns","owner","steward","lineage",
        "governance","certified",
    ],
    QueryIntent.INCIDENT_REVIEW: [
        "jira","open bugs","open issues",
        "incidents","blockers",
    ],
    QueryIntent.KNOWLEDGE_LOOKUP: [
        "what is","what are","how does","how do",
        "explain","describe","define",
    ],
    QueryIntent.METRIC_ANALYSIS: [
        "what is the","how much is","compare",
        "trend","pattern","anomaly",
    ],
}

PRODUCT_KEYWORDS: Dict[str, str] = {
    "retention": "retention",  
    "churn":    "retention",
    "grr":       "retention",  
    "nrr":      "retention",
    "bookings":  "bookings",  
    "revenue":  "bookings",
    "arr":       "bookings",   
    "mrr":      "bookings",
    "cac":       "cac",       
    "payback":  "cac",
    "ltv":       "ltv",        
    "lifetime": "ltv",
}

def classify_intent(query: str) -> str:
    q = query.lower()
    for intent, keywords in INTENT_RULES.items():
        if any(kw in q for kw in keywords):
            return intent.value
    return QueryIntent.UNKNOWN.value

def extract_products(query: str) -> List[str]:
    q        = query.lower()
    products = set()
    for kw, product in PRODUCT_KEYWORDS.items():
        if kw in q:
            products.add(product)
    return list(products) if products else ["retention"]