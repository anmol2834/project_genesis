'use client';

import { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  Checkbox,
  FormControlLabel,
  TextField,
  InputAdornment,
  Chip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  ArrowBackRounded,
  ExpandMoreRounded,
  SearchRounded,
  DescriptionRounded,
  SecurityRounded,
  AccountCircleRounded,
  PaymentRounded,
  CopyrightRounded,
  GavelRounded,
  BlockRounded,
  ExitToAppRounded,
  PublicRounded,
  ContactMailRounded,
  CheckCircleRounded,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { lightGradients, darkGradients } from '@/theme/palette';

const termsData = [
  {
    id: 'introduction',
    title: 'Introduction',
    icon: DescriptionRounded,
    content: `Welcome to Proxipilot, an AI-powered email automation and management platform. By accessing or using our services, you agree to be bound by these Terms and Conditions. Proxipilot provides intelligent email automation, lead management, campaign orchestration, and AI-driven communication tools designed to enhance business productivity and customer engagement.

These terms constitute a legally binding agreement between you (the "User" or "Customer") and Proxipilot ("we," "us," or "our"). Please read these terms carefully before using our platform. If you do not agree with any part of these terms, you must not use our services.`,
  },
  {
    id: 'acceptance',
    title: 'Acceptance of Terms',
    icon: CheckCircleRounded,
    content: `By creating an account, accessing our platform, or using any of our services, you acknowledge that you have read, understood, and agree to be bound by these Terms and Conditions, as well as our Privacy Policy. You also represent that you have the legal authority to enter into this agreement on behalf of yourself or the organization you represent.

If you are using Proxipilot on behalf of a company or organization, you represent and warrant that you have the authority to bind that entity to these terms. In such cases, "you" and "your" will refer to that organization.`,
  },
  {
    id: 'user-responsibilities',
    title: 'User Responsibilities',
    icon: AccountCircleRounded,
    content: `As a user of Proxipilot, you are responsible for:

• Maintaining the confidentiality of your account credentials and API keys
• Ensuring all information provided during registration is accurate and up-to-date
• Complying with all applicable laws and regulations in your use of the platform
• Using the service only for lawful business purposes
• Not sharing your account access with unauthorized individuals
• Promptly notifying us of any unauthorized access or security breaches
• Ensuring your email campaigns comply with anti-spam laws (CAN-SPAM, GDPR, etc.)
• Respecting intellectual property rights and not uploading infringing content
• Maintaining appropriate data backup and security measures for your business data

You acknowledge that you are solely responsible for all activities conducted through your account, and we will not be liable for any loss or damage arising from your failure to maintain account security.`,
  },
  {
    id: 'privacy-data',
    title: 'Privacy & Data Usage',
    icon: SecurityRounded,
    content: `Proxipilot is committed to protecting your privacy and handling your data responsibly. Our data practices include:

Data Collection: We collect information necessary to provide our services, including account details, email content, contact lists, campaign data, and usage analytics.

Data Usage: Your data is used to deliver our AI-powered automation services, improve platform functionality, provide customer support, and enhance user experience. We employ advanced AI models to analyze communication patterns and optimize email campaigns.

Data Security: We implement industry-standard security measures including encryption, secure data storage, access controls, and regular security audits to protect your information.

Third-Party Integration: When you connect third-party services (email providers, CRM systems), we access only the data necessary to provide our services and comply with those platforms' terms of service.

Data Retention: We retain your data for as long as your account is active or as needed to provide services. You may request data deletion in accordance with our Privacy Policy.

For detailed information about our data practices, please review our comprehensive Privacy Policy available on our website.`,
  },
  {
    id: 'account-rules',
    title: 'Account Rules & Guidelines',
    icon: GavelRounded,
    content: `To maintain a secure and professional platform, users must adhere to the following account rules:

Account Creation: You must provide accurate, complete, and current information during registration. Accounts created with false or misleading information may be suspended or terminated.

Account Security: You are responsible for maintaining strong passwords and enabling two-factor authentication when available. Do not share your login credentials with others.

Account Usage: Each account is licensed for use by a single organization or individual. Multi-user access should be managed through proper team member invitations and role-based permissions.

Account Suspension: We reserve the right to suspend or terminate accounts that violate these terms, engage in fraudulent activity, abuse our services, or pose security risks to our platform or other users.

Account Termination: You may terminate your account at any time through your account settings. Upon termination, your data will be handled according to our data retention policies.`,
  },
  {
    id: 'subscription-billing',
    title: 'Subscription & Billing Policies',
    icon: PaymentRounded,
    content: `Proxipilot operates on a subscription-based pricing model with the following policies:

Subscription Plans: We offer various subscription tiers with different features, usage limits, and pricing. Plan details are available on our pricing page.

Billing Cycles: Subscriptions are billed on a monthly or annual basis, depending on your selected plan. Billing occurs automatically at the start of each billing cycle.

Payment Methods: We accept major credit cards and other payment methods as indicated during checkout. You authorize us to charge your payment method for all fees incurred.

Price Changes: We reserve the right to modify subscription prices with at least 30 days' notice. Price changes will apply to subsequent billing cycles.

Refund Policy: Refunds are provided on a case-by-case basis and are generally not available for partial billing periods. Please contact our support team for refund requests.

Free Trials: Free trial periods may be offered for new users. Credit card information may be required, and you will be charged automatically when the trial ends unless you cancel before the trial expiration.

Cancellation: You may cancel your subscription at any time. Cancellations take effect at the end of the current billing period, and you will retain access until that time.

Usage Limits: Each plan includes specific usage limits (email sends, contacts, AI requests). Exceeding these limits may result in additional charges or service restrictions.`,
  },
  {
    id: 'intellectual-property',
    title: 'Intellectual Property Rights',
    icon: CopyrightRounded,
    content: `All intellectual property rights related to Proxipilot remain our exclusive property:

Platform Ownership: Proxipilot, including all software, algorithms, AI models, designs, trademarks, logos, and documentation, is owned by us and protected by intellectual property laws.

User Content: You retain ownership of all content you upload, create, or transmit through our platform (emails, contact lists, campaign materials). By using our services, you grant us a limited license to process, store, and transmit your content solely for the purpose of providing our services.

AI-Generated Content: Content generated by our AI systems based on your inputs and data remains your property. However, we retain the right to use anonymized, aggregated data to improve our AI models and services.

Restrictions: You may not copy, modify, reverse engineer, decompile, or create derivative works of our platform or proprietary technology. You may not remove or alter any proprietary notices or labels.

Feedback: Any feedback, suggestions, or ideas you provide about our services may be used by us without obligation or compensation to you.`,
  },
  {
    id: 'limitation-liability',
    title: 'Limitation of Liability',
    icon: SecurityRounded,
    content: `To the maximum extent permitted by law, Proxipilot's liability is limited as follows:

Service Availability: We strive to maintain high uptime and reliability but do not guarantee uninterrupted or error-free service. We are not liable for service disruptions, data loss, or business interruptions.

Indirect Damages: We are not liable for any indirect, incidental, consequential, special, or punitive damages, including lost profits, lost revenue, lost data, or business interruption.

Maximum Liability: Our total liability for any claims arising from your use of our services is limited to the amount you paid us in the 12 months preceding the claim.

AI Accuracy: While our AI systems are designed to be accurate and helpful, we do not guarantee the accuracy, completeness, or reliability of AI-generated content or recommendations. You are responsible for reviewing and verifying all AI outputs.

Third-Party Services: We are not responsible for the performance, availability, or actions of third-party services integrated with our platform.

User Conduct: We are not liable for damages arising from your violation of these terms, misuse of our services, or unlawful conduct.`,
  },
  {
    id: 'prohibited-activities',
    title: 'Prohibited Activities',
    icon: BlockRounded,
    content: `The following activities are strictly prohibited when using Proxipilot:

Illegal Activities: Using our platform for any illegal purpose, including fraud, money laundering, or distribution of illegal content.

Spam & Abuse: Sending unsolicited bulk emails (spam), violating anti-spam laws (CAN-SPAM, GDPR), or engaging in email harvesting or scraping.

Malicious Content: Distributing malware, viruses, phishing attempts, or other harmful code through our platform.

Harassment: Using our services to harass, threaten, defame, or abuse others.

Unauthorized Access: Attempting to gain unauthorized access to our systems, other users' accounts, or connected third-party services.

System Interference: Interfering with or disrupting our platform's operation, servers, or networks.

Data Mining: Scraping, crawling, or mining data from our platform without authorization.

Impersonation: Impersonating others or misrepresenting your affiliation with any person or organization.

Competitive Use: Using our platform to develop competing products or services.

Violation of these prohibitions may result in immediate account suspension or termination, and we may report illegal activities to law enforcement authorities.`,
  },
  {
    id: 'termination',
    title: 'Termination Policy',
    icon: ExitToAppRounded,
    content: `Either party may terminate this agreement under the following conditions:

User Termination: You may terminate your account at any time by canceling your subscription through your account settings or contacting our support team.

Our Termination Rights: We may suspend or terminate your account immediately if you violate these terms, engage in fraudulent activity, abuse our services, fail to pay fees, or pose security risks.

Effect of Termination: Upon termination, your access to the platform will cease, and we may delete your data according to our retention policies. You remain responsible for all fees incurred before termination.

Data Export: Before termination, you should export any data you wish to retain. We may provide a limited grace period for data export, but we are not obligated to retain your data after termination.

Survival: Provisions related to intellectual property, limitation of liability, indemnification, and dispute resolution survive termination of this agreement.`,
  },
  {
    id: 'governing-law',
    title: 'Governing Law & Dispute Resolution',
    icon: PublicRounded,
    content: `These Terms and Conditions are governed by the following legal framework:

Governing Law: These terms are governed by and construed in accordance with the laws of the jurisdiction in which Proxipilot is registered, without regard to conflict of law principles.

Dispute Resolution: Any disputes arising from these terms or your use of our services will be resolved through binding arbitration, except where prohibited by law. You waive the right to participate in class action lawsuits.

Jurisdiction: If arbitration is not applicable, disputes will be resolved in the courts of our registered jurisdiction, and you consent to the exclusive jurisdiction of those courts.

Informal Resolution: Before initiating formal dispute resolution, you agree to contact us to attempt to resolve the dispute informally.

Legal Fees: In any dispute resolution proceeding, the prevailing party may be entitled to recover reasonable attorney's fees and costs.`,
  },
  {
    id: 'modifications',
    title: 'Modifications to Terms',
    icon: DescriptionRounded,
    content: `We reserve the right to modify these Terms and Conditions at any time:

Notice of Changes: We will provide notice of material changes through email, platform notifications, or by posting the updated terms on our website.

Effective Date: Changes become effective 30 days after notice is provided, unless otherwise specified.

Continued Use: Your continued use of our services after changes take effect constitutes acceptance of the modified terms.

Rejection of Changes: If you do not agree to modified terms, you must discontinue use of our services and may terminate your account.

Version History: We maintain a version history of our terms, which is available upon request.`,
  },
  {
    id: 'contact',
    title: 'Contact Information',
    icon: ContactMailRounded,
    content: `If you have questions, concerns, or need support regarding these Terms and Conditions:

Email Support: support@Proxipilot.com
Business Inquiries: business@Proxipilot.com
Legal Inquiries: legal@Proxipilot.com

Mailing Address:
Proxipilot Inc.
114 - Siddhivinayak Socity 2, Mora Tekra, Hazira Road
Surat, Gujarat, 394517
India

Support Hours: Monday - Friday, 9:00 AM - 6:00 PM (Your Timezone)

We strive to respond to all inquiries within 24-48 business hours. For urgent matters, please indicate "URGENT" in your subject line.

Last Updated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`,
  },
];

const quickNavItems = [
  { label: 'Introduction', id: 'introduction' },
  { label: 'Acceptance', id: 'acceptance' },
  { label: 'User Responsibilities', id: 'user-responsibilities' },
  { label: 'Privacy & Data', id: 'privacy-data' },
  { label: 'Account Rules', id: 'account-rules' },
  { label: 'Billing', id: 'subscription-billing' },
  { label: 'Intellectual Property', id: 'intellectual-property' },
  { label: 'Liability', id: 'limitation-liability' },
  { label: 'Prohibited Activities', id: 'prohibited-activities' },
  { label: 'Termination', id: 'termination' },
  { label: 'Governing Law', id: 'governing-law' },
  { label: 'Modifications', id: 'modifications' },
  { label: 'Contact', id: 'contact' },
];

export default function TermsPage() {
  const router = useRouter();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const grad = isDark ? darkGradients : lightGradients;

  const [searchQuery, setSearchQuery] = useState('');
  const [expanded, setExpanded] = useState<string | false>('introduction');
  const [agreed, setAgreed] = useState(false);
  const [activeNav, setActiveNav] = useState('introduction');

  const handleAccordionChange = (panel: string) => (_: React.SyntheticEvent, isExpanded: boolean) => {
    setExpanded(isExpanded ? panel : false);
  };

  const filteredTerms = termsData.filter(
    (term) =>
      term.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      term.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const scrollToSection = (id: string) => {
    setExpanded(id);
    const element = document.getElementById(`section-${id}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: theme.palette.background.default,
        pb: 4,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1000,
          background: alpha(theme.palette.background.paper, 0.9),
          backdropFilter: 'blur(20px)',
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Container maxWidth="lg">
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              py: 2,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <IconButton
                onClick={() => router.back()}
                sx={{
                  background: alpha(theme.palette.primary.main, 0.1),
                  '&:hover': { background: alpha(theme.palette.primary.main, 0.2) },
                }}
              >
                <ArrowBackRounded />
              </IconButton>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
                  Terms & Conditions
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.7rem' }}>
                  Last updated: {new Date().toLocaleDateString()}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ mt: 3 }}>
        {/* Hero Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Box
            sx={{
              background: grad.primary,
              borderRadius: 3,
              p: { xs: 3, sm: 4 },
              mb: 3,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ position: 'relative', zIndex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <DescriptionRounded sx={{ fontSize: 32, color: 'white' }} />
                <Typography variant="h4" sx={{ fontWeight: 700, color: 'white', fontSize: { xs: '1.5rem', sm: '2rem' } }}>
                  Legal Agreement
                </Typography>
              </Box>
              <Typography sx={{ color: 'rgba(255,255,255,0.9)', fontSize: '0.9rem', maxWidth: 600 }}>
                Please read these terms carefully. By using Proxipilot, you agree to be bound by these terms and conditions.
                This agreement protects both you and us.
              </Typography>
            </Box>
          </Box>
        </motion.div>

        {/* Search Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <TextField
            fullWidth
            placeholder="Search terms..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchRounded sx={{ color: 'text.secondary' }} />
                </InputAdornment>
              ),
            }}
            sx={{
              mb: 3,
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
                background: theme.palette.background.paper,
              },
            }}
          />
        </motion.div>

        {/* Quick Navigation */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <Box sx={{ mb: 3, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {quickNavItems.map((item) => (
              <Chip
                key={item.id}
                label={item.label}
                onClick={() => {
                  scrollToSection(item.id);
                  setActiveNav(item.id);
                }}
                sx={{
                  background: activeNav === item.id ? grad.primary : alpha(theme.palette.primary.main, 0.1),
                  color: activeNav === item.id ? 'white' : 'text.primary',
                  fontWeight: 500,
                  fontSize: '0.75rem',
                  '&:hover': {
                    background: activeNav === item.id ? grad.primary : alpha(theme.palette.primary.main, 0.15),
                  },
                }}
              />
            ))}
          </Box>
        </motion.div>

        {/* Terms Sections */}
        <Box sx={{ mb: 4 }}>
          <AnimatePresence>
            {filteredTerms.map((term, index) => {
              const Icon = term.icon;
              return (
                <motion.div
                  key={term.id}
                  id={`section-${term.id}`}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: index * 0.05 }}
                >
                  <Accordion
                    expanded={expanded === term.id}
                    onChange={handleAccordionChange(term.id)}
                    sx={{
                      mb: 1.5,
                      borderRadius: 2,
                      background: theme.palette.background.paper,
                      border: `1px solid ${theme.palette.divider}`,
                      '&:before': { display: 'none' },
                      boxShadow: expanded === term.id ? `0 4px 20px ${alpha(theme.palette.primary.main, 0.1)}` : 'none',
                    }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreRounded />}
                      sx={{
                        '& .MuiAccordionSummary-content': {
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1.5,
                          my: 1,
                        },
                      }}
                    >
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: 2,
                          background: alpha(theme.palette.primary.main, 0.1),
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Icon sx={{ fontSize: 20, color: 'primary.main' }} />
                      </Box>
                      <Typography sx={{ fontWeight: 600, fontSize: '0.95rem' }}>{term.title}</Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: 0, pb: 3, px: 3 }}>
                      <Typography
                        sx={{
                          color: 'text.secondary',
                          fontSize: '0.85rem',
                          lineHeight: 1.8,
                          whiteSpace: 'pre-line',
                        }}
                      >
                        {term.content}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </Box>

        {/* Agreement Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Box
            sx={{
              background: theme.palette.background.paper,
              borderRadius: 3,
              p: 3,
              border: `1px solid ${theme.palette.divider}`,
            }}
          >
            <FormControlLabel
              control={
                <Checkbox
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  sx={{
                    '&.Mui-checked': {
                      color: 'primary.main',
                    },
                  }}
                />
              }
              label={
                <Typography sx={{ fontSize: '0.9rem', color: 'text.primary' }}>
                  I have read and agree to the Terms & Conditions
                </Typography>
              }
            />
            <Button
              fullWidth
              variant="contained"
              disabled={!agreed}
              onClick={() => router.push('/')}
              sx={{
                mt: 2,
                py: 1.5,
                background: agreed ? grad.primary : undefined,
                fontWeight: 600,
                fontSize: '0.9rem',
                '&:hover': {
                  background: agreed ? grad.primary : undefined,
                  filter: 'brightness(1.1)',
                },
              }}
            >
              Accept & Continue
            </Button>
          </Box>
        </motion.div>
      </Container>
    </Box>
  );
}
