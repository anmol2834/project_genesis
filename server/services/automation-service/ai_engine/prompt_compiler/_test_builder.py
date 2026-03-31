"""Quick validation test for the prompt compiler."""
import asyncio
import sys
import types
import importlib.util
import os

base = os.path.join(os.path.dirname(__file__), "..")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


for pkg in ["ai_engine", "ai_engine.schemas", "ai_engine.context_builder",
            "ai_engine.preprocess", "ai_engine.policy_engine", "ai_engine.prompt_compiler"]:
    if pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = []
        sys.modules[pkg] = m

load(f"{base}/schemas/intent_schema.py",      "ai_engine.schemas.intent_schema")
load(f"{base}/schemas/ai_input.py",           "ai_engine.schemas.ai_input")
load(f"{base}/preprocess/processor.py",       "ai_engine.preprocess.processor")
load(f"{base}/context_builder/schema.py",     "ai_engine.context_builder.schema")
load(f"{base}/policy_engine/rules.py",        "ai_engine.policy_engine.rules")
load(f"{base}/policy_engine/schema.py",       "ai_engine.policy_engine.schema")
load(f"{base}/prompt_compiler/schema.py",     "ai_engine.prompt_compiler.schema")
load(f"{base}/prompt_compiler/templates.py",  "ai_engine.prompt_compiler.templates")
load(f"{base}/prompt_compiler/formatter.py",  "ai_engine.prompt_compiler.formatter")
load(f"{base}/prompt_compiler/optimizer.py",  "ai_engine.prompt_compiler.optimizer")
load(f"{base}/prompt_compiler/builder.py",    "ai_engine.prompt_compiler.builder")

from ai_engine.prompt_compiler.builder import PromptBuilder
from ai_engine.prompt_compiler.schema import PromptMode
from ai_engine.context_builder.schema import SelectedContext
from ai_engine.preprocess.processor import PreprocessedInput
from ai_engine.schemas.intent_schema import (
    IntentResult, IntentType, SubIntent, SentimentType, LanguageType, RiskFlag,
)
from ai_engine.policy_engine.rules import PolicyAction
from ai_engine.policy_engine.schema import (
    PolicyDecision, CONSTRAINTS_FULL, CONSTRAINTS_SAFE, CONSTRAINTS_ABUSE, CONSTRAINTS_MINIMAL,
)


def make_ctx(has_knowledge=True, has_conv=False, summary=""):
    return SelectedContext(
        business_instruction=(
            "You are an AI assistant for MailFlowAI. Business Name: MailFlowAI"
            if has_knowledge else ""
        ),
        business_core="We provide AI-powered email automation for sales teams." if has_knowledge else "",
        tone_guidance="Professional and helpful.",
        use_case_context="Sales outreach, lead nurturing, customer support.",
        conversation_summary=summary,
        recent_history_text=(
            "[From sender]: What does it cost?\n[Our reply]: Plans start at 49/month."
            if has_conv else ""
        ),
        total_context_tokens=80,
    )


def make_intent(intent, sub=SubIntent.NONE, sentiment=SentimentType.NEUTRAL,
                flags=None, secondary=None):
    return IntentResult(
        intent=intent, sub_intent=sub, sentiment=sentiment,
        language_type=LanguageType.INFORMAL, confidence=0.82,
        risk_flags=flags or [RiskFlag.NONE],
        secondary_intents=secondary or [],
    )


def make_policy(action, constraints=None, safe=False, human=False):
    return PolicyDecision(
        action=action, matched_rule_id="TEST", reason="test",
        constraints=constraints or CONSTRAINTS_FULL,
        is_safe_mode=safe, requires_human=human,
    )


def make_preprocessed(content, subject=""):
    return PreprocessedInput(
        user_id="u1", email_account_id="a1", conversation_id="c1",
        thread_id="t1", subject=subject, clean_incoming_content=content,
        clean_history=[], message_summary="", token_budget_remaining=3000,
    )


CASES = [
    (
        "Pricing query",
        make_ctx(has_knowledge=True),
        make_intent(IntentType.QUESTION, SubIntent.PRICING),
        make_policy(PolicyAction.ALLOW),
        make_preprocessed("What is your pricing?", "Pricing"),
        PromptMode.STANDARD,
    ),
    (
        "Objection",
        make_ctx(has_knowledge=True),
        make_intent(IntentType.OBJECTION, SubIntent.TRUST),
        make_policy(PolicyAction.SAFE_MODE, CONSTRAINTS_SAFE, safe=True),
        make_preprocessed("I am not sure this is worth it", "Re: Offer"),
        PromptMode.SAFE,
    ),
    (
        "Abuse message",
        make_ctx(has_knowledge=True),
        make_intent(IntentType.COMPLAINT, flags=[RiskFlag.ABUSE_PATTERN],
                    sentiment=SentimentType.ABUSIVE),
        make_policy(PolicyAction.SAFE_MODE, CONSTRAINTS_ABUSE, safe=True),
        make_preprocessed("Your service is trash", ""),
        PromptMode.ABUSE,
    ),
    (
        "Casual chat",
        make_ctx(has_knowledge=True),
        make_intent(IntentType.REPLY, SubIntent.CASUAL_CHAT),
        make_policy(PolicyAction.ALLOW),
        make_preprocessed("hello", ""),
        PromptMode.STANDARD,
    ),
    (
        "No context",
        make_ctx(has_knowledge=False),
        make_intent(IntentType.QUESTION),
        make_policy(PolicyAction.ALLOW),
        make_preprocessed("What do you offer?", ""),
        PromptMode.NO_CONTEXT,
    ),
    (
        "Mixed intent + conv history",
        make_ctx(has_knowledge=True, has_conv=True, summary="Prospect asked about pricing."),
        make_intent(IntentType.INTEREST, SubIntent.PRICING,
                    secondary=[IntentType.QUESTION]),
        make_policy(P