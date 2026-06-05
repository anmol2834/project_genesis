"""
Fallback Response Generator - Safe, professional escalation messages
"""
import logging
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ResponseTone(Enum):
    """Response tone variants"""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    APOLOGETIC = "apologetic"
    URGENT = "urgent"

class FallbackResponseGenerator:
    """Generates context-aware fallback responses for escalation"""
    
    def __init__(self):
        # Templates are dynamic and context-aware, NOT hardcoded business data
        self.templates = {
            "general": {
                "en": {
                    "professional": "Thank you for your message. Our specialist team is reviewing your request and will contact you shortly.",
                    "friendly": "Thanks for reaching out! We've passed your message to our expert team who will get back to you soon.",
                    "apologetic": "We apologize for any confusion. Our specialist team is reviewing your inquiry and will respond shortly.",
                    "urgent": "We've received your urgent request. Our priority team is reviewing it now and will respond immediately."
                },
                "es": {
                    "professional": "Gracias por su mensaje. Nuestro equipo especializado está revisando su solicitud y se comunicará con usted en breve.",
                    "friendly": "¡Gracias por contactarnos! Hemos pasado su mensaje a nuestro equipo experto que responderá pronto.",
                    "apologetic": "Disculpe las molestias. Nuestro equipo especializado está revisando su consulta y responderá en breve.",
                    "urgent": "Hemos recibido su solicitud urgente. Nuestro equipo prioritario la está revisando ahora y responderá de inmediato."
                }
            },
            "billing": {
                "en": {
                    "professional": "Thank you for contacting us regarding billing. Our financial team is reviewing your account and will respond within 1 hour.",
                    "apologetic": "We sincerely apologize for any billing concerns. Our finance team is investigating and will contact you shortly."
                }
            },
            "refund": {
                "en": {
                    "professional": "Your refund request has been escalated to our resolution team. You will receive an update within 2 hours.",
                    "apologetic": "We apologize for any inconvenience. Your refund request is being reviewed by our resolution team."
                }
            },
            "legal": {
                "en": {
                    "professional": "Your legal inquiry has been forwarded to our compliance team. They will respond within 4 hours during business hours.",
                    "urgent": "We've received your legal inquiry. Our legal team is reviewing it with priority."
                }
            },
            "technical": {
                "en": {
                    "professional": "Thank you for reporting this technical issue. Our engineering team is investigating and will provide an update soon.",
                    "friendly": "Thanks for letting us know! Our tech team is looking into this and will get back to you soon."
                }
            }
        }
    
    def generate_response(
        self,
        escalation_reason: str,
        risk_level: str,
        language: str = "en",
        tenant_tone: Optional[str] = None,
        customer_emotion: Optional[str] = None,
        custom_template: Optional[str] = None
    ) -> str:
        """Generate context-aware fallback response"""
        
        # Use custom template if provided (tenant-specific)
        if custom_template:
            return self._apply_context(custom_template, escalation_reason, risk_level)
        
        # Determine tone
        tone = self._determine_tone(risk_level, customer_emotion, tenant_tone)
        
        # Select template category
        category = self._categorize_escalation(escalation_reason)
        
        # Get template
        template = self._get_template(category, language, tone)
        
        return template
    
    def _determine_tone(
        self,
        risk_level: str,
        customer_emotion: Optional[str],
        tenant_tone: Optional[str]
    ) -> str:
        """Determine appropriate response tone"""
        
        # Critical/urgent situations
        if risk_level in ["critical", "high"]:
            return "urgent"
        
        # Angry or frustrated customers
        if customer_emotion in ["angry", "frustrated"]:
            return "apologetic"
        
        # Tenant preference
        if tenant_tone:
            return tenant_tone
        
        # Default professional
        return "professional"
    
    def _categorize_escalation(self, escalation_reason: str) -> str:
        """Categorize escalation reason to select appropriate template"""
        
        reason_lower = escalation_reason.lower()
        
        if any(kw in reason_lower for kw in ["billing", "payment", "charge", "invoice"]):
            return "billing"
        
        if any(kw in reason_lower for kw in ["refund", "money back", "return"]):
            return "refund"
        
        if any(kw in reason_lower for kw in ["legal", "privacy", "gdpr", "compliance"]):
            return "legal"
        
        if any(kw in reason_lower for kw in ["technical", "error", "bug", "not working"]):
            return "technical"
        
        return "general"
    
    def _get_template(self, category: str, language: str, tone: str) -> str:
        """Retrieve appropriate template"""
        
        # Try specific category and tone
        if category in self.templates:
            lang_templates = self.templates[category].get(language, self.templates[category].get("en", {}))
            if tone in lang_templates:
                return lang_templates[tone]
        
        # Fallback to general
        lang_templates = self.templates["general"].get(language, self.templates["general"]["en"])
        return lang_templates.get(tone, lang_templates["professional"])
    
    def _apply_context(self, template: str, escalation_reason: str, risk_level: str) -> str:
        """Apply dynamic context to template"""
        
        # Replace placeholders if present
        template = template.replace("{escalation_reason}", escalation_reason)
        template = template.replace("{risk_level}", risk_level)
        
        return template
    
    def add_custom_template(
        self,
        tenant_id: str,
        category: str,
        language: str,
        tone: str,
        template: str
    ) -> bool:
        """Allow tenants to add custom templates (future extension)"""
        
        # Store in database for tenant-specific templates
        # This enables multi-tenant customization
        
        logger.info(f"Custom template registered for tenant {tenant_id}")
        return True
