from abc import ABC, abstractmethod
from decimal import Decimal

from .models import Decision, MarketSnapshot, Side


class DecisionEngine(ABC):
    @abstractmethod
    async def decide(self, snapshot: MarketSnapshot) -> Decision: ...


class MockDecisionEngine(DecisionEngine):
    def __init__(self, action: Side = Side.HOLD):
        self.action = action

    async def decide(self, snapshot: MarketSnapshot) -> Decision:
        return Decision(self.action, "mock deterministic decision", Decimal("1"))


class GeminiDecisionEngine(DecisionEngine):
    """Interface placeholder. It never owns sizing or risk configuration."""
    async def decide(self, snapshot: MarketSnapshot) -> Decision:
        raise NotImplementedError("connect Gemini locally after human review")

