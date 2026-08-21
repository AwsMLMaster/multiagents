"""
Intent Registry for USA Property Finder Assistant.

This module defines all supported intents with their configurations,
including required parameters, target agents, and tools.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class IntentCategory(str, Enum):
    """High-level intent categories."""
    SEARCH = "search"
    PROPERTY = "property"
    VALUATION = "valuation"
    MORTGAGE = "mortgage"
    NEIGHBORHOOD = "neighborhood"
    MARKET = "market"
    SCHEDULING = "scheduling"
    RAG = "rag"
    GENERAL = "general"


@dataclass
class IntentDefinition:
    """Definition of a single intent."""
    id: str
    category: IntentCategory
    description: str
    target_agent: str
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    enabled: bool = True
    feature_flag: Optional[str] = None


# ============================================================================
# Intent Registry
# ============================================================================

INTENT_REGISTRY: Dict[str, IntentDefinition] = {
    # =========================================================================
    # Search Intents
    # =========================================================================
    "search.properties": IntentDefinition(
        id="search.properties",
        category=IntentCategory.SEARCH,
        description="Search for properties matching location/price/feature criteria",
        target_agent="search_agent",
        tools=["search_listings", "geocode_location"],
        required_params=["location"],
        optional_params=[
            "price_min", "price_max", "bedrooms_min", "bathrooms_min",
            "property_types", "min_sqft", "features",
        ],
        examples=[
            "Find 3 bedroom homes in Austin, TX under $500,000",
            "Show me condos near downtown Seattle",
            "I'm looking for a house with a pool in Phoenix",
            "Search for townhouses in Denver between $300k and $450k",
            "What's available in the 90210 zip code?",
        ],
    ),

    "search.refine": IntentDefinition(
        id="search.refine",
        category=IntentCategory.SEARCH,
        description="Refine the current search results with additional filters",
        target_agent="search_agent",
        tools=["refine_search"],
        optional_params=["price_min", "price_max", "bedrooms_min", "features", "sort_by"],
        examples=[
            "Only show me ones with a garage",
            "Narrow it down to under $400k",
            "Sort by newest listings",
            "Just single family homes please",
        ],
    ),

    "search.save": IntentDefinition(
        id="search.save",
        category=IntentCategory.SEARCH,
        description="Save the current search criteria for future alerts",
        target_agent="search_agent",
        tools=["save_search", "create_alert"],
        examples=[
            "Save this search",
            "Alert me when new listings match this",
            "Notify me about new homes in this area",
        ],
    ),

    # =========================================================================
    # Property Detail Intents
    # =========================================================================
    "property.details": IntentDefinition(
        id="property.details",
        category=IntentCategory.PROPERTY,
        description="Get full details on a specific property",
        target_agent="property_details_agent",
        tools=["get_property_details", "get_photos", "get_price_history"],
        required_params=["property_id"],
        examples=[
            "Tell me more about the second listing",
            "Show me details on 123 Main St",
            "What's the square footage of that house?",
            "Show me photos of this property",
            "What's the price history on this one?",
        ],
    ),

    "property.compare": IntentDefinition(
        id="property.compare",
        category=IntentCategory.PROPERTY,
        description="Compare two or more properties side by side",
        target_agent="property_details_agent",
        tools=["compare_properties"],
        required_params=["property_ids"],
        examples=[
            "Compare the first and third listings",
            "Which of these two has a bigger yard?",
            "Compare these properties side by side",
        ],
    ),

    "property.favorite": IntentDefinition(
        id="property.favorite",
        category=IntentCategory.PROPERTY,
        description="Save a property to favorites",
        target_agent="property_details_agent",
        tools=["save_favorite", "remove_favorite"],
        required_params=["property_id"],
        examples=[
            "Save this to my favorites",
            "Add this house to my list",
            "Remove this from my favorites",
        ],
    ),

    # =========================================================================
    # Valuation Intents
    # =========================================================================
    "valuation.estimate": IntentDefinition(
        id="valuation.estimate",
        category=IntentCategory.VALUATION,
        description="Get an automated value estimate (AVM) for a property",
        target_agent="valuation_agent",
        tools=["get_avm_estimate", "get_tax_assessment"],
        required_params=["property_id_or_address"],
        examples=[
            "What's this house worth?",
            "Give me a value estimate for 456 Oak Ave",
            "What's the Zestimate-style value on this?",
            "Is this house priced fairly?",
        ],
    ),

    "valuation.comps": IntentDefinition(
        id="valuation.comps",
        category=IntentCategory.VALUATION,
        description="Get comparable recent sales for a property",
        target_agent="valuation_agent",
        tools=["get_comparable_sales"],
        required_params=["property_id_or_address"],
        examples=[
            "Show me comparable sales nearby",
            "What have similar homes sold for recently?",
            "Show me comps for this property",
        ],
    ),

    # =========================================================================
    # Mortgage Intents
    # =========================================================================
    "mortgage.calculate": IntentDefinition(
        id="mortgage.calculate",
        category=IntentCategory.MORTGAGE,
        description="Calculate estimated monthly mortgage payment",
        target_agent="mortgage_agent",
        tools=["calculate_payment"],
        required_params=["price", "down_payment"],
        optional_params=["interest_rate", "loan_term_years", "property_tax_rate", "hoa_fees"],
        examples=[
            "What would my monthly payment be on a $400,000 house?",
            "Calculate mortgage payment with 20% down",
            "How much is the monthly payment with a 30-year loan?",
        ],
    ),

    "mortgage.affordability": IntentDefinition(
        id="mortgage.affordability",
        category=IntentCategory.MORTGAGE,
        description="Estimate how much home the buyer can afford",
        target_agent="mortgage_agent",
        tools=["calculate_affordability"],
        required_params=["annual_income"],
        optional_params=["monthly_debts", "down_payment_available", "credit_score_band"],
        examples=[
            "How much house can I afford with an $85,000 salary?",
            "What's my price range with $50k saved for a down payment?",
            "Am I pre-qualified for a $350,000 home?",
        ],
    ),

    "mortgage.rates": IntentDefinition(
        id="mortgage.rates",
        category=IntentCategory.MORTGAGE,
        description="Get current average mortgage interest rates",
        target_agent="mortgage_agent",
        tools=["get_current_rates"],
        examples=[
            "What are current mortgage rates?",
            "What's the average 30-year fixed rate today?",
            "Are rates going up or down?",
        ],
    ),

    # =========================================================================
    # Neighborhood Intents
    # =========================================================================
    "neighborhood.overview": IntentDefinition(
        id="neighborhood.overview",
        category=IntentCategory.NEIGHBORHOOD,
        description="Get neighborhood overview: schools, safety, walkability, amenities",
        target_agent="neighborhood_agent",
        tools=["get_school_ratings", "get_crime_stats", "get_walkability", "get_amenities"],
        required_params=["location"],
        examples=[
            "What's this neighborhood like?",
            "How are the schools around here?",
            "Is this area safe?",
            "What's the walkability score?",
            "What amenities are nearby?",
        ],
    ),

    "neighborhood.commute": IntentDefinition(
        id="neighborhood.commute",
        category=IntentCategory.NEIGHBORHOOD,
        description="Estimate commute time from a property to a destination",
        target_agent="neighborhood_agent",
        tools=["estimate_commute"],
        required_params=["origin", "destination"],
        examples=[
            "How long would my commute to downtown be?",
            "What's the drive time to the airport?",
            "Is this close to public transit?",
        ],
    ),

    # =========================================================================
    # Market Trends Intents
    # =========================================================================
    "market.trends": IntentDefinition(
        id="market.trends",
        category=IntentCategory.MARKET,
        description="Get price trends and market temperature for an area",
        target_agent="market_trends_agent",
        tools=["get_price_trends", "get_market_temperature"],
        required_params=["location"],
        examples=[
            "How's the housing market in Austin?",
            "Are home prices rising in this area?",
            "Is this a buyer's or seller's market?",
            "What's the median home price here?",
        ],
    ),

    "market.forecast": IntentDefinition(
        id="market.forecast",
        category=IntentCategory.MARKET,
        description="Get market forecast and days-on-market statistics",
        target_agent="market_trends_agent",
        tools=["get_market_forecast", "get_days_on_market"],
        required_params=["location"],
        examples=[
            "Will prices keep going up here?",
            "How fast are homes selling in this area?",
            "What's the forecast for next year?",
        ],
    ),

    # =========================================================================
    # Scheduling Intents
    # =========================================================================
    "scheduling.tour": IntentDefinition(
        id="scheduling.tour",
        category=IntentCategory.SCHEDULING,
        description="Schedule a property tour or showing",
        target_agent="scheduling_agent",
        tools=["schedule_tour", "check_availability"],
        required_params=["property_id"],
        optional_params=["preferred_date", "preferred_time", "tour_type"],
        examples=[
            "Schedule a tour for this weekend",
            "Can I see this house on Saturday?",
            "Book a showing for tomorrow at 3pm",
            "Set up a virtual tour",
        ],
    ),

    "scheduling.contact_agent": IntentDefinition(
        id="scheduling.contact_agent",
        category=IntentCategory.SCHEDULING,
        description="Contact the listing agent about a property",
        target_agent="scheduling_agent",
        tools=["contact_listing_agent"],
        required_params=["property_id"],
        examples=[
            "Connect me with the listing agent",
            "I have a question for the seller's agent",
            "Can someone call me about this listing?",
        ],
    ),

    # =========================================================================
    # RAG / General Knowledge Intents
    # =========================================================================
    "rag.general": IntentDefinition(
        id="rag.general",
        category=IntentCategory.RAG,
        description="General real estate knowledge questions and buying/renting process guidance",
        target_agent="rag_agent",
        tools=["knowledge_base_query"],
        examples=[
            "What's the difference between pre-qualified and pre-approved?",
            "What is escrow?",
            "How does the home buying process work?",
            "What's a HOA?",
            "What is earnest money?",
        ],
    ),

    "rag.terminology": IntentDefinition(
        id="rag.terminology",
        category=IntentCategory.RAG,
        description="Explain real estate terminology",
        target_agent="rag_agent",
        tools=["knowledge_base_query"],
        examples=[
            "What does contingent mean?",
            "What is a 1031 exchange?",
            "Explain PMI",
            "What does 'under contract' mean?",
        ],
    ),

    # =========================================================================
    # General Intents
    # =========================================================================
    "general.greeting": IntentDefinition(
        id="general.greeting",
        category=IntentCategory.GENERAL,
        description="Greeting",
        target_agent="rag_agent",
        examples=["Hello", "Hi there", "Good morning", "Hey"],
    ),

    "general.help": IntentDefinition(
        id="general.help",
        category=IntentCategory.GENERAL,
        description="Help request",
        target_agent="rag_agent",
        examples=[
            "What can you help me with?",
            "How does this work?",
            "What can you do?",
        ],
    ),
}


def get_intent(intent_id: str) -> Optional[IntentDefinition]:
    """Get intent definition by ID."""
    return INTENT_REGISTRY.get(intent_id)


def get_intents_by_category(category: IntentCategory) -> List[IntentDefinition]:
    """Get all intents in a category."""
    return [
        intent for intent in INTENT_REGISTRY.values()
        if intent.category == category and intent.enabled
    ]


def get_intents_for_agent(agent: str) -> List[IntentDefinition]:
    """Get all intents handled by an agent."""
    return [
        intent for intent in INTENT_REGISTRY.values()
        if intent.target_agent == agent and intent.enabled
    ]


def get_all_examples() -> Dict[str, List[str]]:
    """Get all examples for testing/classifier prompt construction."""
    return {
        intent_id: intent.examples
        for intent_id, intent in INTENT_REGISTRY.items()
        if intent.enabled
    }


def add_custom_intent(intent: IntentDefinition) -> None:
    """Add a custom intent to the registry."""
    INTENT_REGISTRY[intent.id] = intent


def disable_intent(intent_id: str) -> bool:
    """Disable an intent."""
    if intent_id in INTENT_REGISTRY:
        INTENT_REGISTRY[intent_id].enabled = False
        return True
    return False


def enable_intent(intent_id: str) -> bool:
    """Enable an intent."""
    if intent_id in INTENT_REGISTRY:
        INTENT_REGISTRY[intent_id].enabled = True
        return True
    return False
