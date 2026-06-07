'use client';

import { useState, useEffect } from 'react';
import { Box, Typography, Container, IconButton, Chip, Collapse, useTheme, alpha, Checkbox, FormControlLabel, Button } from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import ShieldRoundedIcon from '@mui/icons-material/ShieldRounded';
import LockRoundedIcon from '@mui/icons-material/LockRounded';
import VerifiedUserRoundedIcon from '@mui/icons-material/VerifiedUserRounded';
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import PaymentRoundedIcon from '@mui/icons-material/PaymentRounded';
import PublicRoundedIcon from '@mui/icons-material/PublicRounded';
import ChildCareRoundedIcon from '@mui/icons-material/ChildCareRounded';
import UpdateRoundedIcon from '@mui/icons-material/UpdateRounded';
import EmailRoundedIcon from '@mui/icons-material/EmailRounded';
import CookieRoundedIcon from '@mui/icons-material/CookieRounded';
import ShareRoundedIcon from '@mui/icons-material/ShareRounded';
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { useRouter } from 'next/navigation';
import { lightGradients, darkGradients } from '@/theme/palette';

const MotionBox = motion.create(Box);

interface Section {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: React.ReactNode;
}

export default function PrivacyPage() {
  const theme = useTheme();
  const router = useRouter();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;
  
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState<string>('intro');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['intro']));
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const toggleSection = (id: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const sections: Section[] = [
    {
      id: 'intro',
      title: 'Introduction',
      icon: <ShieldRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            Welcome to Proxipilot. We are committed to protecting your privacy and ensuring the security of your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your data when you use our AI-powered email automation platform.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary' }}>
            By using Proxipilot, you agree to the collection and use of information in accordance with this policy. We encourage you to read this document carefully to understand our practices.
          </Typography>
        </>
      ),
    },
    {
      id: 'collection',
      title: 'Information We Collect',
      icon: <StorageRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Personal Information:</Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Account details (name, email, phone number)<br />
            • Business information (company name, industry, size)<br />
            • Profile data and preferences<br />
            • Communication history and interactions
          </Typography>
          
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Email Data:</Typography>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Email content, metadata, and attachments<br />
            • Contact lists and lead information<br />
            • Campaign performance metrics<br />
            • Email engagement analytics
          </Typography>

          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1, color: 'text.primary' }}>Technical Data:</Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Device information and IP addresses<br />
            • Browser type and operating system<br />
            • Usage patterns and feature interactions<br />
            • Log files and diagnostic data
          </Typography>
        </>
      ),
    },
    {
      id: 'usage',
      title: 'How We Use Your Information',
      icon: <PersonRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We use your information to provide, maintain, and improve our services:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Deliver AI-powered email automation and personalization<br />
            • Process and analyze email campaigns<br />
            • Provide customer support and respond to inquiries<br />
            • Send service updates and important notifications<br />
            • Improve our AI models and platform features<br />
            • Detect and prevent fraud or security threats<br />
            • Comply with legal obligations and enforce our terms<br />
            • Conduct research and analytics to enhance user experience
          </Typography>
        </>
      ),
    },
    {
      id: 'security',
      title: 'Data Storage & Security',
      icon: <LockRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We implement industry-leading security measures to protect your data:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
            {['AES-256 Encryption', 'TLS/SSL', 'SOC 2 Compliant', 'GDPR Ready'].map(badge => (
              <Chip key={badge} label={badge} size="small" sx={{ 
                fontSize: '0.7rem', 
                height: 24,
                background: alpha(theme.palette.success.main, 0.1),
                color: theme.palette.success.main,
                fontWeight: 600
              }} />
            ))}
          </Box>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • End-to-end encryption for sensitive data<br />
            • Regular security audits and penetration testing<br />
            • Secure data centers with 24/7 monitoring<br />
            • Multi-factor authentication (MFA) support<br />
            • Role-based access controls (RBAC)<br />
            • Automated backup and disaster recovery systems<br />
            • Employee security training and background checks
          </Typography>
        </>
      ),
    },
    {
      id: 'cookies',
      title: 'Cookies & Tracking',
      icon: <CookieRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We use cookies and similar technologies to enhance your experience:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Essential cookies for platform functionality<br />
            • Analytics cookies to understand usage patterns<br />
            • Preference cookies to remember your settings<br />
            • Marketing cookies for personalized content
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            You can control cookie preferences through your browser settings. Note that disabling certain cookies may limit platform functionality.
          </Typography>
        </>
      ),
    },
    {
      id: 'third-party',
      title: 'Third-Party Services',
      icon: <ShareRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We integrate with trusted third-party services to enhance our platform:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Email service providers (Gmail, Outlook, etc.)<br />
            • Payment processors (Stripe, PayPal)<br />
            • Cloud infrastructure providers (AWS, Google Cloud)<br />
            • Analytics and monitoring tools<br />
            • AI and machine learning services<br />
            • Customer support platforms
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            These partners are contractually obligated to protect your data and use it only for specified purposes. We carefully vet all third-party integrations.
          </Typography>
        </>
      ),
    },
    {
      id: 'rights',
      title: 'Your Rights & Controls',
      icon: <VerifiedUserRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            You have comprehensive rights regarding your personal data:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • <strong>Access:</strong> Request a copy of your data<br />
            • <strong>Rectification:</strong> Correct inaccurate information<br />
            • <strong>Erasure:</strong> Request deletion of your data<br />
            • <strong>Portability:</strong> Export your data in standard formats<br />
            • <strong>Restriction:</strong> Limit how we process your data<br />
            • <strong>Objection:</strong> Opt-out of certain data processing<br />
            • <strong>Withdraw Consent:</strong> Revoke permissions at any time
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            To exercise these rights, contact us at hello@proxipilot.com. We will respond within 30 days.
          </Typography>
        </>
      ),
    },
    {
      id: 'payment',
      title: 'Payment Information',
      icon: <PaymentRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            Payment data is handled with the highest security standards:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • We do not store full credit card numbers<br />
            • Payment processing via PCI-DSS compliant providers<br />
            • Tokenization for secure recurring payments<br />
            • Encrypted transmission of all financial data<br />
            • Regular security audits of payment systems
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            Billing information is retained only as long as necessary for accounting and legal compliance.
          </Typography>
        </>
      ),
    },
    {
      id: 'sharing',
      title: 'Data Sharing Policies',
      icon: <PublicRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We do not sell your personal information. We may share data only in these circumstances:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • With your explicit consent<br />
            • To comply with legal obligations or court orders<br />
            • To protect our rights, property, or safety<br />
            • With service providers under strict confidentiality agreements<br />
            • In connection with business transfers (mergers, acquisitions)<br />
            • Aggregated, anonymized data for research purposes
          </Typography>
        </>
      ),
    },
    {
      id: 'children',
      title: 'Child Privacy Protection',
      icon: <ChildCareRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            Proxipilot is not intended for children under 16 years of age. We do not knowingly collect personal information from children.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary' }}>
            If we discover that a child under 16 has provided us with personal information, we will promptly delete it from our systems. Parents or guardians who believe their child has provided us with information should contact us immediately.
          </Typography>
        </>
      ),
    },
    {
      id: 'international',
      title: 'International Data Transfers',
      icon: <PublicRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            Your data may be transferred to and processed in countries outside your residence:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • We use Standard Contractual Clauses (SCCs) approved by the EU<br />
            • Data transfers comply with GDPR and other privacy regulations<br />
            • We ensure adequate protection regardless of location<br />
            • Primary data centers located in secure jurisdictions
          </Typography>
        </>
      ),
    },
    {
      id: 'retention',
      title: 'Data Retention Policy',
      icon: <UpdateRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We retain your data only as long as necessary:
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary', pl: 2 }}>
            • Active account data: Duration of service use<br />
            • Deleted account data: 90 days (for recovery)<br />
            • Email campaign data: 2 years or as configured<br />
            • Financial records: 7 years (legal requirement)<br />
            • Analytics data: Aggregated and anonymized indefinitely
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            You can request early deletion by contacting our support team.
          </Typography>
        </>
      ),
    },
    {
      id: 'updates',
      title: 'Policy Updates',
      icon: <UpdateRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            We may update this Privacy Policy periodically to reflect changes in our practices or legal requirements.
          </Typography>
          <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.secondary' }}>
            Material changes will be communicated via email or prominent notice on our platform at least 30 days before taking effect. Continued use after changes constitutes acceptance of the updated policy.
          </Typography>
        </>
      ),
    },
    {
      id: 'contact',
      title: 'Contact Information',
      icon: <EmailRoundedIcon sx={{ fontSize: 18 }} />,
      content: (
        <>
          <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.7, color: 'text.secondary' }}>
            For questions, concerns, or requests regarding this Privacy Policy:
          </Typography>
          <Box sx={{ 
            p: 2, 
            borderRadius: 2, 
            background: alpha(theme.palette.primary.main, 0.05),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`
          }}>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: 'text.primary' }}>Email:</Typography>
            <Typography variant="body2" sx={{ mb: 1.5, color: 'primary.main' }}>hello@proxipilot.com</Typography>
            
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: 'text.primary' }}>Data Protection Officer:</Typography>
            <Typography variant="body2" sx={{ mb: 1.5, color: 'text.secondary' }}>hello@proxipilot.com</Typography>
            
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5, color: 'text.primary' }}>Response Time:</Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>Within 30 days of receipt</Typography>
          </Box>
        </>
      ),
    },
  ];

  return (
    <Box sx={{ 
      minHeight: '100vh', 
      background: theme.palette.background.default,
      pb: 0
    }}>
      {/* Header */}
      <Box sx={{ 
        position: 'sticky', 
        top: 0, 
        zIndex: 100,
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        background: scrolled 
          ? alpha(theme.palette.background.default, 0.85)
          : 'transparent',
        borderBottom: scrolled ? `1px solid ${theme.palette.divider}` : 'none',
        transition: 'all 0.3s ease'
      }}>
        <Container maxWidth="lg" sx={{ py: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton 
              onClick={() => router.back()}
              sx={{ 
                background: alpha(theme.palette.primary.main, 0.08),
                '&:hover': { background: alpha(theme.palette.primary.main, 0.15) }
              }}
            >
              <ArrowBackRoundedIcon sx={{ fontSize: 20 }} />
            </IconButton>
            <Box sx={{ flex: 1 }}>
              <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: 'text.primary' }}>
                Privacy Policy
              </Typography>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>
                Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </Typography>
            </Box>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: 3, px: 2 }}>
        {/* Hero Section */}
        <MotionBox
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          sx={{ mb: 3 }}
        >
          <Box sx={{ 
            p: 3,
            borderRadius: 3,
            background: grad.primary,
            color: '#fff',
            textAlign: 'center',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <Box sx={{ position: 'relative', zIndex: 1 }}>
              <SecurityRoundedIcon sx={{ fontSize: 48, mb: 1.5, opacity: 0.9 }} />
              <Typography sx={{ fontWeight: 700, fontSize: '1.3rem', mb: 1 }}>
                Your Privacy Matters
              </Typography>
              <Typography sx={{ fontSize: '0.85rem', opacity: 0.95, maxWidth: 500, mx: 'auto' }}>
                We're committed to protecting your data with enterprise-grade security and transparent practices.
              </Typography>
            </Box>
          </Box>
        </MotionBox>

        {/* Trust Badges */}
        <MotionBox
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          sx={{ mb: 3 }}
        >
          <Box sx={{ 
            display: 'flex', 
            gap: 1.5, 
            justifyContent: 'center',
            flexWrap: 'wrap'
          }}>
            {[
              { icon: <LockRoundedIcon />, label: 'Encrypted' },
              { icon: <VerifiedUserRoundedIcon />, label: 'GDPR Compliant' },
              { icon: <ShieldRoundedIcon />, label: 'SOC 2' }
            ].map((badge, i) => (
              <Box key={i} sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 0.75,
                px: 2,
                py: 1,
                borderRadius: 2,
                background: alpha(theme.palette.success.main, 0.08),
                border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`
              }}>
                <Box sx={{ color: theme.palette.success.main, display: 'flex', fontSize: 16 }}>
                  {badge.icon}
                </Box>
                <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: theme.palette.success.main }}>
                  {badge.label}
                </Typography>
              </Box>
            ))}
          </Box>
        </MotionBox>

        {/* Sections */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {sections.map((section, index) => (
            <MotionBox
              key={section.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: index * 0.05 }}
            >
              <Box sx={{ 
                borderRadius: 2.5,
                border: `1px solid ${theme.palette.divider}`,
                background: theme.palette.background.paper,
                overflow: 'hidden',
                transition: 'all 0.2s ease',
                '&:hover': {
                  boxShadow: theme.shadows[2]
                }
              }}>
                <Box 
                  onClick={() => toggleSection(section.id)}
                  sx={{ 
                    p: 2,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    cursor: 'pointer',
                    userSelect: 'none'
                  }}
                >
                  <Box sx={{ 
                    width: 36,
                    height: 36,
                    borderRadius: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: alpha(theme.palette.primary.main, 0.1),
                    color: theme.palette.primary.main,
                    flexShrink: 0
                  }}>
                    {section.icon}
                  </Box>
                  <Typography sx={{ 
                    flex: 1, 
                    fontWeight: 600, 
                    fontSize: '0.9rem',
                    color: 'text.primary'
                  }}>
                    {section.title}
                  </Typography>
                  <ExpandMoreRoundedIcon sx={{ 
                    fontSize: 20,
                    color: 'text.disabled',
                    transform: expandedSections.has(section.id) ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.3s ease'
                  }} />
                </Box>
                
                <Collapse in={expandedSections.has(section.id)}>
                  <Box sx={{ px: 2, pb: 2, pt: 0 }}>
                    <Box sx={{ 
                      pl: 6.5,
                      pr: 1
                    }}>
                      {section.content}
                    </Box>
                  </Box>
                </Collapse>
              </Box>
            </MotionBox>
          ))}
        </Box>

        {/* Consent Section */}
        <MotionBox
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          sx={{ mt: 4, mb: 3 }}
        >
          <Box sx={{ 
            p: 3,
            borderRadius: 3,
            border: `1px solid ${theme.palette.divider}`,
            background: theme.palette.background.paper
          }}>
            <FormControlLabel
              control={
                <Checkbox 
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  sx={{ 
                    '& .MuiSvgIcon-root': { fontSize: 20 }
                  }}
                />
              }
              label={
                <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>
                  I have read and understood the Privacy Policy
                </Typography>
              }
            />
            <Button
              fullWidth
              disabled={!agreed}
              onClick={() => router.back()}
              sx={{ 
                mt: 2,
                py: 1.25,
                borderRadius: 2,
                background: agreed ? grad.primary : theme.palette.action.disabledBackground,
                color: '#fff',
                fontWeight: 600,
                fontSize: '0.9rem',
                textTransform: 'none',
                '&:hover': {
                  background: agreed ? grad.primary : theme.palette.action.disabledBackground,
                  filter: agreed ? 'brightness(1.1)' : 'none'
                },
                '&:disabled': {
                  color: theme.palette.text.disabled
                }
              }}
            >
              Accept & Continue
            </Button>
          </Box>
        </MotionBox>
      </Container>
    </Box>
  );
}
